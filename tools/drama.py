#!/usr/bin/env python3
"""Multi-voice ("radio drama") rendering of a paragraph range — the listening trial.

Usage: drama.py <episode_dir> --from P034 --to P059 --mode half|full|single
Reads script/script.json, script/speakers.json ({"P035": "holmes", ...} — who speaks the 「」 quotes of that
 paragraph; a list gives one speaker per top-level quote), script/cast.json ({"narrator": voice_id, ...})
Writes drama/<mode>/{NNN.wav,plan.json}, drama/<mode>.m4a (−14 LUFS, ≤ −1 dBTP, like assemble.py)

half = only Holmes gets his own voice; everyone else stays with the narrator
full = every tagged speaker gets the voice cast for them (Watson's own lines stay with the narrator: he is the narrator)
single = the existing block audio of the same range (no API calls), for A/B
"""
import argparse, json, subprocess, sys, time, wave
from pathlib import Path

import mm
from tts import paced
from assemble import loudness, last_json, TARGET_I, TARGET_LRA, MASTER_TP, DELIVERY_TP

IN_PARA, BETWEEN_PARA = 0.35, 1.5   # seconds: narrator ↔ quote inside a paragraph / paragraph pause


def runs(text):
    """Split into narration ('N') and top-level 「…」 quote ('Q') runs; inner 『』 and nested 「」 stay inside."""
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch == "「":
            if depth == 0:
                if cur:
                    out.append(("N", cur))
                cur = ""
                depth = 1
                continue
            depth += 1
        elif ch == "」":
            depth -= 1
            if depth == 0:
                out.append(("Q", cur)); cur = ""
                continue
        cur += ch
    if cur:
        out.append(("N", cur))
    return out


def role(cast, name):
    """cast.json values: a voice_id, or {"voice": id, "emotion": "calm" | null} (null = let the model read the line)."""
    r = cast[name]
    return (r, "calm") if isinstance(r, str) else (r["voice"], r.get("emotion"))


def voice_for(speaker, mode, cast):
    if mode == "half":
        return role(cast, "holmes") if speaker == "holmes" else role(cast, "narrator")
    if speaker in (None, "watson", "narrator") or speaker not in cast:
        return role(cast, "narrator")
    return role(cast, speaker)


def plan(ep, first, last, mode):
    rows = json.loads((ep / "script/script.json").read_text())
    ids = [r["id"] for r in rows]
    rows = rows[ids.index(first):ids.index(last) + 1]
    tags = json.loads((ep / "script/speakers.json").read_text())
    cast = json.loads((ep / "script/cast.json").read_text())
    pieces = []   # (voice, text, gap_after)
    for r in rows:
        who = tags.get(r["id"])
        q = 0
        for k, t in runs(r["zh"]):
            if k == "Q":
                spk = who[q] if isinstance(who, list) else who
                q += 1
                v = voice_for(spk, mode, cast)
                # the narrator voice keeps the quote marks (reads as reported speech); a character voice speaks the line bare
                pieces.append([v, t if v != role(cast, "narrator") else f"「{t}」", IN_PARA])
            else:
                pieces.append([role(cast, "narrator"), t, IN_PARA])
        pieces[-1][2] = BETWEEN_PARA
    # merge consecutive same-voice pieces into one request; the pause travels inside as <#s#>
    calls = []
    for v, t, gap in pieces:
        if calls and (calls[-1]["voice"], calls[-1]["emotion"]) == v:
            calls[-1]["text"] += f"<#{calls[-1]['gap']}#>" + paced(t)
            calls[-1]["gap"] = gap
        else:
            calls.append({"voice": v[0], "emotion": v[1], "text": paced(t), "gap": gap})
    return calls


def synth(call, cfg, wav):
    v = cfg["voice"]
    for attempt in range(8):
        r = mm.call("POST", f"{mm.HOST}/v1/t2a_v2", {
            "model": v["model"], "text": call["text"], "stream": False, "output_format": "url",
            "language_boost": "Chinese",
            "voice_setting": {"voice_id": call["voice"], "speed": v["speed"], "vol": 1, "pitch": 0,
                              **({"emotion": call["emotion"]} if call.get("emotion") else {})},
            "audio_setting": {"sample_rate": 44100, "format": "wav", "channel": 1},
            "pronunciation_dict": {"tone": v["pronunciation"]}}, timeout=240)
        br = r.get("base_resp", {})
        if br.get("status_code") in (1002, 1039):
            time.sleep(min(60, 5 * 2 ** attempt)); continue
        break
    if br.get("status_code") != 0 or not (r.get("data") or {}).get("audio"):
        raise RuntimeError(f"{wav.name}: {br}")
    wav.write_bytes(mm.fetch_bytes(r["data"]["audio"], timeout=300))
    return r["extra_info"]["usage_characters"]


def trimmed(frames, pad=0.06):
    """Each T2A clip carries ~0.3–0.45 s of silence at both ends; between a quote and 「他說」 that doubled the gap."""
    import numpy as np
    a = np.frombuffer(frames, dtype=np.int16)
    loud = np.where(np.abs(a.astype(np.int32)) > 0.02 * 32768)[0]
    if not len(loud):
        return frames
    p = int(pad * 44100)
    return a[max(0, loud[0] - p):loud[-1] + p].tobytes()


def join(wavs_gaps, out, trim=True):
    with wave.open(str(out), "wb") as o:
        o.setnchannels(1); o.setsampwidth(2); o.setframerate(44100)
        for path, gap in wavs_gaps:
            with wave.open(str(path)) as w:
                assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (44100, 1, 2), path
                f = w.readframes(w.getnframes())
            o.writeframes(trimmed(f) if trim else f)
            o.writeframes(b"\0\0" * int(44100 * gap))


def master(raw, m4a):
    tmp48 = raw.with_suffix(".48k.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af", "aresample=48000,pan=stereo|c0=c0|c1=c0",
                    "-c:a", "pcm_s24le", str(tmp48)], check=True)
    p1 = loudness(tmp48, full=True)
    ln = (f"loudnorm=I={TARGET_I}:TP={MASTER_TP}:LRA={TARGET_LRA}:measured_I={p1['input_i']}:"
          f"measured_TP={p1['input_tp']}:measured_LRA={p1['input_lra']}:measured_thresh={p1['input_thresh']}:"
          f"offset={p1['target_offset']}:linear=true:print_format=json")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp48), "-af", ln, "-ar", "48000",
                    "-c:a", "aac", "-b:a", "256k", str(m4a)], check=True)
    tmp48.unlink()
    i, tp = loudness(m4a)
    return {"I": i, "TP": tp, "ok": tp <= DELIVERY_TP and abs(i - TARGET_I) <= 0.5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ep"); ap.add_argument("--from", dest="first", required=True)
    ap.add_argument("--to", dest="last", required=True); ap.add_argument("--mode", required=True)
    a = ap.parse_args()
    ep = Path(a.ep).expanduser().resolve()
    cfg = json.loads((ep / "episode.json").read_text())
    out = ep / "drama" / a.mode
    out.mkdir(parents=True, exist_ok=True)
    if a.mode == "single":
        tl = json.loads((ep / "audio/timeline.json").read_text())
        blocks = [s for s in tl if s["paras"] and a.first <= s["paras"][0] and s["paras"][-1] <= a.last]
        assert blocks and blocks[0]["paras"][0] == a.first and blocks[-1]["paras"][-1] == a.last, "range must be whole blocks"
        parts = [(ep / "audio/seg" / f"{b['id']}.wav", nb["gap_before"] if nb else 0)
                 for b, nb in zip(blocks, blocks[1:] + [None])]
        chars = 0
    else:
        calls = plan(ep, a.first, a.last, a.mode)
        (out / "plan.json").write_text(json.dumps(calls, ensure_ascii=False, indent=1))
        parts, chars = [], 0
        for n, c in enumerate(calls, 1):
            wav = out / f"{n:03d}.wav"
            meta = out / f"{n:03d}.txt"
            if not (wav.exists() and meta.exists() and meta.read_text() == f"{c['voice']}|{c.get('emotion')}\n{c['text']}"):
                chars += synth(c, cfg, wav)
                meta.write_text(f"{c['voice']}|{c.get('emotion')}\n{c['text']}")
            print(f"  {n}/{len(calls)} {c['voice'].split('_', 1)[-1]}", flush=True)
            parts.append((wav, c["gap"]))
    raw = out / "raw.wav"
    join(parts, raw, trim=a.mode != "single")
    res = master(raw, ep / "drama" / f"{a.mode}.m4a")
    with wave.open(str(raw)) as w:
        res["seconds"] = round(w.getnframes() / 44100, 1)
    res["billed_characters"] = chars
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
