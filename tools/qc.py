#!/usr/bin/env python3
"""Narration QC without listening: pace outliers for every segment + Whisper round-trip on a sample.

Usage: qc.py <episode_dir> [SEGMENT_ID ...]
Reads audio/timeline.json (segments and the paragraphs each one speaks).
"""
import json, re, statistics, subprocess, sys
from pathlib import Path

WHISPER = __import__("os").environ.get("WHISPER_BIN") or __import__("shutil").which("whisper") or "whisper"


def han(s):
    return re.findall(r"[〇㐀-鿿]", s)


def digits_to_han(s):
    # Whisper writes 一八九〇年十月九日 as 1890年10月9日; spelled digit by digit the length and the
    # ending line up again, where before episode 1 failed QC on two perfectly read dates
    # episode 29 B001: amounts are read by place value (五千英鎊 → Whisper 5000) and spelled digit by
    # digit they never match 一千 at the ending — so only years (3–4 digits before 年) stay digit by digit
    D = "〇一二三四五六七八九"

    def place(n):
        if n >= 10000:
            hi, lo = divmod(n, 10000)
            return place(hi) + "萬" + ("零" if 0 < lo < 1000 else "") + (place(lo) if lo else "")
        out, zero = "", False
        for v, u in ((1000, "千"), (100, "百"), (10, "十"), (1, "")):
            d, n = divmod(n, v)
            if d:
                out += ("零" if zero and out else "") + ("" if (u == "十" and d == 1 and not out) else D[d]) + u
                zero = False
            else:
                zero = True
        return out or "零"

    def sub(m):
        t = m.group(0)
        if (len(t) >= 3 and s[m.end():m.end() + 1] == "年") or t.startswith("0") or len(t) > 8:
            return t.translate(str.maketrans("0123456789", D))
        return place(int(t))
    return re.sub(r"\d+", sub, s)


def cer(ref, hyp):
    # character error rate by edit distance
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / max(len(ref), 1)


def cut_tail(ref, hyp):
    # Whisper pads the last 30 s window and hallucinates video outros past the real end
    # (「请不吝点赞 订阅 转发」 after episode 6 B019, whose narration is complete) — cut the transcript right
    # after the reference ending once it appears; a truncated reading never shows the ending, so it still fails
    # the ending is matched as loosely as ends_ok judges it (last 6 chars, CER ≤ 0.5): Whisper writes 伯明罕 as
    # 博明汉 and 著 as 着, and an exact match missed both (episodes 16 B007, 12 B011)
    # — and the closest window wins, not the first loose one (a first-hit cut episode 6 B010 at 988 of 1089 chars)
    end = ref[-6:]
    spots = [(cer(end, hyp[k:k + len(end)]), k) for k in range(max(0, int(len(ref) * 0.8) - 6), len(hyp) - len(end) + 1)]
    d, k = min(spots, default=(1.0, 0))
    return hyp[:k + len(end)] if d <= 0.5 else hyp


def main():
    ep = Path(sys.argv[1]).expanduser()
    cfg = json.loads((ep / "episode.json").read_text())
    zh = {r["id"]: r["zh"] for r in json.loads((ep / "script" / "script.json").read_text())}
    timeline = json.loads((ep / "audio" / "timeline.json").read_text())
    text = {}
    for s in timeline:
        if s["id"] in ("INTRO", "OUTRO"):
            text[s["id"]] = re.sub(r"<#[\d.]+#>", "", cfg[s["id"].lower()])
        else:
            text[s["id"]] = "".join(zh[p] for p in s["paras"])
    seg = ep / "audio" / "seg"
    # pace: CJK characters per second of audio (explicit pauses slow short segments, so flag gently)
    pace = {sid: len(han(t)) / (json.loads((seg / f"{sid}.meta.json").read_text())["audio_ms"] / 1000)
            for sid, t in text.items()}
    mu, sd = statistics.mean(pace.values()), statistics.pstdev(pace.values())
    outliers = sorted((sid for sid, p in pace.items() if abs(p - mu) > 2.5 * sd and len(han(text[sid])) >= 15),
                      key=lambda s: pace[s])[:3]
    body = [s["id"] for s in timeline if s["id"] not in ("INTRO", "OUTRO")]
    k = 3 if body[0].startswith("B") else 8          # blocks are minutes long; paragraphs are seconds
    spread = [body[round(i * (len(body) - 1) / (k - 1))] for i in range(k)]
    sample = list(dict.fromkeys((sys.argv[2:] or ["INTRO"] + spread + ["OUTRO"]) + outliers))
    asr_dir = ep / "build" / "asr"
    asr_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for sid in sample:
        txt, wav = asr_dir / f"{sid}.txt", seg / f"{sid}.wav"
        if not txt.exists() or txt.stat().st_mtime < wav.stat().st_mtime:  # re-recorded → re-transcribe
            subprocess.run(["nice", "-n", "10", WHISPER, str(wav), "--model", "large-v3-turbo", "--model_dir",
                            str(Path.home() / ".cache/whisper"), "--language", "zh", "--output_format", "txt",
                            "--output_dir", str(asr_dir), "--fp16", "False", "--verbose", "False"],
                           capture_output=True, check=True)
        hyp_s = subprocess.run(["opencc", "-c", "s2t"], input=txt.read_text(), capture_output=True,
                               text=True, check=True).stdout
        ref, hyp = han(text[sid]), han(digits_to_han(hyp_s))
        hyp = cut_tail(ref, hyp)
        calls = json.loads((seg / f"{sid}.meta.json").read_text()).get("calls")
        # episode 102 B015: the whole-block pass dropped 「就這樣保留了下來」 right before the ending
        # (the last clip reads it back) — a missed ending gets the per-clip check too, not only a short transcript
        ends = "".join(ref[-3:]) in "".join(hyp[-8:]) or cer(ref[-6:], hyp[-6:]) <= 0.5
        if calls and (len(hyp) < 0.9 * len(ref) or not ends):
            # episode 13 B001: Whisper silently skipped a whole 25 s Holmes line inside a 3-minute
            # multi-voice block (the clip itself reads back word for word). A drama block is a chain of
            # separate T2A clips, so transcribe each clip on its own and judge the joined text instead
            parts = []
            for k in calls:
                ct = asr_dir / "calls" / f"{k}.txt"
                cw = ep / "audio" / "calls" / f"{k}.wav"
                if not ct.exists():
                    subprocess.run(["nice", "-n", "10", WHISPER, str(cw), "--model", "large-v3-turbo",
                                    "--model_dir", str(Path.home() / ".cache/whisper"), "--language", "zh",
                                    "--output_format", "txt", "--output_dir", str(asr_dir / "calls"),
                                    "--fp16", "False", "--verbose", "False"], capture_output=True, check=True)
                parts.append(ct.read_text())
            joined = subprocess.run(["opencc", "-c", "s2t"], input="".join(parts), capture_output=True,
                                    text=True, check=True).stdout
            hyp = cut_tail(ref, han(digits_to_han(joined)))
        results.append({"id": sid, "ref_chars": len(ref), "asr_chars": len(hyp), "cer": round(cer(ref, hyp), 3),
                        "ends_ok": "".join(ref[-3:]) in "".join(hyp[-8:]) or cer(ref[-6:], hyp[-6:]) <= 0.5,
                        "pace_cps": round(pace[sid], 2)})
    report = {"pace_mean_cps": round(mu, 2), "pace_sd": round(sd, 2), "pace_outliers": outliers,
              "sample": results, "mean_cer": round(statistics.mean(r["cer"] for r in results), 3)}
    (ep / "build" / "qc-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
