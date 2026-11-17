#!/usr/bin/env python3
"""Multi-voice ("full radio drama") narration for a whole episode — drop-in for tts.py.

Usage: drama_tts.py <episode_dir> [--dry-run]
Reads script/script.json, episode.json, script/speakers.json ({"P035": "holmes", "P050": ["king", "holmes"]}:
 who speaks the top-level 「」 of that paragraph; a list = one speaker per quote; untagged = narrator),
 ../../cast-default.json (series voices) + optional script/cast.json (this episode's roles)
Writes the same files tts.py writes — audio/seg/{INTRO,Bnnn,OUTRO}.{wav,sub.json,meta.json}, audio/timeline.json,
 audio/tts-manifest.json — so assemble.py / qc.py / package.py run unchanged; plus script/cast.resolved.json.
 Every T2A call is cached in audio/calls/<sha1 of voice, emotion, text, voice settings>.{wav,sub.json,json}.

Blocks, scene gaps and INTRO/OUTRO are tts.plan's; inside a block the text is cut at top-level 「」, each run goes
to its speaker's voice, same-voice neighbours are merged into one request, and the ~0.3–0.45 s of silence T2A puts
at both ends of every clip is trimmed (drama.trimmed) so a quote and 「他說」 stay 0.35 s apart, not a second.
"""
import hashlib, json, re, sys, threading, time, wave
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

import mm
from drama import runs as _runs, IN_PARA
from tts import paced, plan as block_plan

SR = 44100
ROOT = Path(__file__).resolve().parent.parent


# T2A allows ~12 requests in a burst, then answers 1002 and the exponential backoff stalled the run for
# 7.5 minutes (20 calls in 493 s); pacing request starts keeps it under the per-minute limit instead
PACE_S = 3.5
_pace_lock, _last = threading.Lock(), [0.0]


def paced_start():
    with _pace_lock:
        wait = _last[0] + PACE_S - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def runs(text):
    """drama.runs, plus the English convention for a speech spanning paragraphs: every paragraph opens 「 and only
 the last one closes it. drama.runs leaves that open tail as narration, so Wilson's whole account (episode 1
 P040–P065) and Holmes's wedding story (episode 2 P133–P141) went to the narrator's voice."""
    out, depth = _runs(text), 0
    for ch in text:
        depth += (ch == "「") - (ch == "」")
    if depth > 0 and out and out[-1][0] == "N":
        out[-1] = ("Q", out[-1][1])
    return out


EXCLUSIVE = {"江戶川亂步": ("akechi",), "阿嘉莎·克莉絲蒂": ("poirot", "marple", "quin", "satterthwaite", "japp"),
             "卻斯特頓": ("brown", "flambeau"),
             "莫里斯·盧布朗": ("lupin", "ganimard", "sholmes", "wilson", "beautrelet", "bechoux"),
             "程小青": ("huosang", "wang"), "奧希茲": ("oldman", "polly"),
             "威爾基·柯林斯": ("cuff", "rachel", "clack"), "范·達因": ("vance", "markham", "heath"),
             "岡本綺堂": ("hanshichi",), "佐佐木味津三": ("umon", "denroku", "keishiro"),
             "洪農": ("raffles",), "本特利": ("trent",), "米恩": ("gillingham", "beverley"),
             "女偵探合輯": ("loveday", "dorcas", "hilda", "molly", "violet"),
             "中國公案": ("di", "bao", "lan"),
             "加博里歐": ("lecoq", "tabaret", "absinthe")}
OWN_REGULARS_ONLY = ("阿嘉莎·克莉絲蒂", "卻斯特頓", "莫里斯·盧布朗", "程小青", "奧希茲", "威爾基·柯林斯", "范·達因", "岡本綺堂", "佐佐木味津三", "洪農", "本特利", "米恩", "女偵探合輯", "中國公案", "加博里歐")     # these seasons never borrow Holmes's recurring keys


class CastError(Exception):
    pass


def resolve_cast(ep, speakers):
    """role → (voice, emotion). Fixed roles are locked; recurring roles keep their series voice; the rest come from
 the episode's cast.json, where "pool:<kind>" takes the first voice of that pool nobody else in the episode has."""
    d = json.loads((ROOT / "cast-default.json").read_text())
    own = json.loads((ep / "script/cast.json").read_text()) if (ep / "script/cast.json").exists() else {}
    # a pool written as {"voice": "pool:…"} (516) was taken for a voice id — dry-run passed, synthesis would not
    own = {k: v["voice"] if isinstance(v, dict) and str(v.get("voice", "")).startswith("pool:") else v
           for k, v in own.items()}
    as_pair = lambda r: (r, None) if isinstance(r, str) else (r["voice"], r.get("emotion"))
    cast = {k: as_pair(v) for k, v in d["fixed"].items()}
    cast["watson"] = cast["narrator"]          # Watson is the one telling the story
    author = json.loads((ep / "episode.json").read_text()).get("author")
    if author in OWN_REGULARS_ONLY:             # Holmes is not in these seasons — and Lupin's Sholmès has his voice
        cast.pop("holmes", None)
    if author in d.get("season_narrator", {}):    # the Vance season is told in a Bailian voice
        cast["narrator"] = cast["watson"] = as_pair(d["season_narrator"][author])
    if author == "阿嘉莎·克莉絲蒂":                 # the first-person tellers of season 3 are the narrator's voice
        for who in ("hastings", "sheppard", "clement"):
            cast[who] = cast["narrator"]
    if author == "程小青":                         # 包朗 tells the 霍桑 stories, like Watson
        cast["baolang"] = cast["narrator"]
    needed = {s for v in speakers.values() for s in (v if isinstance(v, list) else [v]) if s} - set(cast)
    for role in sorted(needed):
        r = own.get(role)
        own_season = author not in OWN_REGULARS_ONLY or role in EXCLUSIVE[author]   # Holmes's mary/king… are
        # another season's regular under the same key (Lupin's Wilson vs the Wilsons of Holmes 67/77, produced and
        # uploaded with their own voices) — a voice the episode's cast.json names outright wins
        foreign = role not in EXCLUSIVE.get(author, ()) and any(role in rs for rs in EXCLUSIVE.values())
        if role in d["recurring"] and own_season and (r is None or not str(r).startswith("pool:")) \
                and not (foreign and r is not None):  # not Christie's
            cast[role] = as_pair(d["recurring"][role])
        elif r is not None and not str(r).startswith("pool:"):
            cast[role] = as_pair(r)
    # a season regular's voice is theirs alone — also when cast.json names it outright (Links/Ackroyd gave
    # Quin's and Satterthwaite's voices to bit parts)
    mine = {d["recurring"][r_]["voice"]: r_ for r_ in EXCLUSIVE.get(author, ())}
    clash = {role: mine[v] for role, (v, _) in cast.items() if v in mine and role != mine[v]}
    if clash:
        raise CastError(f"regular's voice given to another role: {clash}")
    for role in sorted(needed - set(cast)):
        r = own.get(role)
        if r is None:
            raise CastError(f"{role}: no voice — add it to script/cast.json (a voice id or \"pool:<kind>\")")
        kind = r.split(":", 1)[1]
        taken = {v for v, _ in cast.values()}
        for r_ in EXCLUSIVE.get(author, ()):      # Akechi's voice is his alone, even when he is absent;
            taken.add(d["recurring"][r_]["voice"])  # same for the season-3 regulars
        free = [v for v in d["pools"][kind] if v not in taken]
        if not free:
            raise CastError(f"{role}: pool {kind} has no voice left in this episode")
        cast[role] = (free[0], None)
    leaked = {r_: v for r_, (v, _) in cast.items() if str(v).startswith("pool:")}
    if leaked:
        raise CastError(f"pool name used as a voice id: {leaked}")
    return cast


def block_calls(paras, rows, tags, cast, gap_para):
    """[{voice, emotion, text, gap}] for one block; gap = silence after this call."""
    nar = cast["narrator"]
    pieces = []
    for pid in paras:
        who = tags.get(pid)
        quotes = [t for k, t in runs(rows[pid]) if k == "Q"]
        if isinstance(who, list) and len(who) != len(quotes):
            raise CastError(f"{pid}: {len(who)} speakers tagged for {len(quotes)} quotes")
        q, first = 0, len(pieces)
        for k, t in runs(rows[pid]):
            if k == "Q":
                spk = who[q] if isinstance(who, list) else who
                q += 1
                v = cast[spk] if spk else nar
                # the narrator keeps the quote marks (reported speech); a character voice speaks the line bare
                t = t if v != nar else f"「{t}」"
            else:
                v = nar
            if len(pieces) > first and pieces[-1][0] == v:
                pieces[-1][1] += t        # same voice inside a paragraph (大寫的「E」, 「…，」我說): no pause
            else:
                pieces.append([v, t, IN_PARA])
        pieces[-1][2] = gap_para
    calls = []
    for v, t, gap in pieces:
        if calls and (calls[-1]["voice"], calls[-1]["emotion"]) == v:
            calls[-1]["text"] += f"<#{calls[-1]['gap']}#>" + paced(t)
            calls[-1]["gap"] = gap
        else:
            calls.append({"voice": v[0], "emotion": v[1], "text": paced(t), "gap": gap})
    return calls


def key(call, vcfg):
    s = json.dumps([call["voice"], call["emotion"], call["text"], vcfg["model"], vcfg["speed"], vcfg["pitch"],
                    vcfg["pronunciation"]], ensure_ascii=False)
    return hashlib.sha1(s.encode()).hexdigest()[:16]


def synth(call, vcfg, cache):
    k = key(call, vcfg)
    wav, sub, meta = (cache / f"{k}{ext}" for ext in (".wav", ".sub.json", ".json"))
    if wav.exists() and sub.exists() and meta.exists():
        return k, 0
    if not re.search(r"[\w㐀-鿿]", re.sub(r"<#[\d.]+#>", "", call["text"])):
        # Rampo: lines that are only 「…………」 — T2A answers with a zero-length file; a short silence instead
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes(b"\0\0" * int(SR * 0.8))
        sub.write_text("[]"); meta.write_text(json.dumps({**call, "usage_characters": 0, "silence": True}, ensure_ascii=False))
        return k, 0
    if call["voice"].startswith("bailian:"):       # Bailian Token Plan voices (bailian_tts.py)
        import bailian_tts
        chars = bailian_tts.synth(call["text"], call["voice"].split(":", 1)[1], call["emotion"], wav, sub, SR)
        meta.write_text(json.dumps({**call, "usage_characters": 0, "bailian_characters": chars}, ensure_ascii=False))
        return k, 0
    for attempt in range(20):
        paced_start()
        r = mm.call("POST", f"{mm.HOST}/v1/t2a_v2", {
            "model": vcfg["model"], "text": call["text"], "stream": False, "output_format": "url",
            "language_boost": "Chinese",
            "voice_setting": {"voice_id": call["voice"], "speed": vcfg["speed"], "vol": 1, "pitch": vcfg["pitch"],
                              **({"emotion": call["emotion"]} if call["emotion"] else {})},
            "audio_setting": {"sample_rate": SR, "format": "wav", "channel": 1},
            "pronunciation_dict": {"tone": vcfg["pronunciation"]},
            "subtitle_enable": True, "subtitle_type": "sentence"}, timeout=240)
        br = r.get("base_resp", {})
        if br.get("status_code") in (1002, 1039):      # RPM / TPM, arrive as HTTP 200
            print(f"  rate limited ({br.get('status_code')}), retry {attempt + 1}", flush=True)
            time.sleep(20); continue
        break
    data = r.get("data") or {}
    if br.get("status_code") != 0 or not data.get("audio"):
        raise RuntimeError(f"{k} ({call['voice']}): {br}")
    wav.write_bytes(mm.fetch_bytes(data["audio"], timeout=300))
    sub.write_bytes(mm.fetch_bytes(data["subtitle_file"]) if data.get("subtitle_file") else b"[]")
    chars = r["extra_info"]["usage_characters"]
    meta.write_text(json.dumps({**call, "usage_characters": chars}, ensure_ascii=False))
    return k, chars


def trim(a, pad=0.06, floor=0.02):
    """(samples, first kept index): cut T2A's leading/trailing silence down to `pad` seconds (same rule as drama.trimmed)."""
    loud = np.where(np.abs(a.astype(np.int32)) > floor * 32768)[0]
    if not len(loud):
        return a, 0
    s = max(0, loud[0] - int(pad * SR))
    return a[s:loud[-1] + int(pad * SR)], s


def speech_db(a):
    """Level of the voiced part of a clip: mean power of the 50 ms windows within 30 dB of its loudest window."""
    w = int(SR * 0.05)
    k = len(a) // w
    if k == 0:
        return None
    p = (a[:k * w].astype(np.float64).reshape(k, w) ** 2).mean(1)
    db = 10 * np.log10(p + 1e-9)
    loud = db[db > db.max() - 30]
    return 10 * np.log10((10 ** (loud / 10)).mean())


LEVEL = {}      # key → gain (dB); Rampo, every season — see main


def render(seg_id, calls, keys, cache, seg_dir):
    """Concatenate one segment's clips into audio/seg/<id>.wav with a matching .sub.json (times in ms)."""
    out, subs, cur = [], [], 0
    for c, k in zip(calls, keys):
        with wave.open(str(cache / f"{k}.wav")) as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (SR, 1, 2), k
            a = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        a, s = trim(a)
        if LEVEL.get(k):
            a = np.clip(a.astype(np.float64) * 10 ** (LEVEL[k] / 20), -32767, 32767).astype(np.int16)
        off = (cur - s) * 1000 / SR
        for e in json.loads((cache / f"{k}.sub.json").read_text()):
            subs.append({**e, "time_begin": round(max(cur * 1000 / SR, e["time_begin"] + off)),
                         "time_end": round(min((cur + len(a)) * 1000 / SR, e["time_end"] + off))})
        out.append(a); cur += len(a)
        if c is not calls[-1]:
            g = np.zeros(int(c["gap"] * SR), np.int16); out.append(g); cur += len(g)
    with wave.open(str(seg_dir / f"{seg_id}.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(np.concatenate(out).tobytes())
    (seg_dir / f"{seg_id}.sub.json").write_text(json.dumps(subs, ensure_ascii=False))
    return round(cur * 1000 / SR)


def main():
    ep = Path(sys.argv[1]).expanduser().resolve()
    cfg = json.loads((ep / "episode.json").read_text())
    vcfg = cfg["voice"]
    rows = {r["id"]: r["zh"] for r in json.loads((ep / "script/script.json").read_text())}
    tags = json.loads((ep / "script/speakers.json").read_text())
    unknown = sorted(set(tags) - set(rows))
    if unknown:
        raise CastError(f"speakers.json names paragraphs that are not in the script: {unknown[:5]}")
    cast = resolve_cast(ep, tags)
    (ep / "script/cast.resolved.json").write_text(json.dumps(
        {r: {"voice": v, "emotion": e} for r, (v, e) in cast.items()}, ensure_ascii=False, indent=1))
    segs = block_plan(cfg, json.loads((ep / "script/script.json").read_text()))
    nar = cast["narrator"]
    plan = {}
    for s in segs:
        if s["id"] in ("INTRO", "OUTRO"):
            plan[s["id"]] = [{"voice": nar[0], "emotion": nar[1], "text": s["tts"], "gap": 0}]
        else:
            plan[s["id"]] = block_calls(s["paras"], rows, tags, cast, cfg["gaps"]["paragraph_s"])
    todo = {key(c, vcfg): c for cs in plan.values() for c in cs}
    voices = sorted({c["voice"] for c in todo.values()})
    print(f"{len(segs)} segments, {sum(map(len, plan.values()))} calls ({len(todo)} distinct), "
          f"{len(voices)} voices: {', '.join(v.split('_', 1)[-1] for v in voices)}", flush=True)
    if "--dry-run" in sys.argv:
        (ep / "audio").mkdir(exist_ok=True)
        (ep / "audio/drama-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1))
        return
    cache, seg_dir = ep / "audio/calls", ep / "audio/seg"
    cache.mkdir(parents=True, exist_ok=True); seg_dir.mkdir(parents=True, exist_ok=True)
    q0 = mm.quota()
    print(f"quota before {q0}", flush=True)
    t0, billed = time.time(), 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(synth, c, vcfg, cache) for c in todo.values()]
        for n, f in enumerate(as_completed(futs), 1):
            billed += f.result()[1]
            if n % 20 == 0 or n == len(futs):
                print(f"  {n}/{len(futs)} calls in {time.time() - t0:.0f}s", flush=True)
    if True:     # every season (Holmes was 10 dB off)
        # T2A voices come out up to 9 dB apart (Gentle_Youth −30.5 vs
        # Gentleman −21.3 LUFS on the same line). Every non-narrator voice is lifted or lowered as a whole to the
        # narrator's median speech level (±12 dB), so each role keeps its own ups and downs.
        by_voice = {}
        for k, c in todo.items():
            with wave.open(str(cache / f"{k}.wav")) as w:
                lv = speech_db(np.frombuffer(w.readframes(w.getnframes()), np.int16))
            if lv is not None and lv > -60:
                by_voice.setdefault(c["voice"], []).append(lv)
        med = {v: float(np.median(x)) for v, x in by_voice.items()}
        ref, gain = med.get(nar[0]), {}
        if ref is not None:
            gain = {v: max(-12.0, min(12.0, ref - m)) for v, m in med.items() if v != nar[0]}
            LEVEL.update({k: gain[c["voice"]] for k, c in todo.items() if c["voice"] in gain})
            print("level match (dB):", {v.split("_")[-1]: round(g, 1) for v, g in gain.items()}, flush=True)
    manifest = []
    for s in segs:
        calls = plan[s["id"]]
        keys = [key(c, vcfg) for c in calls]
        ms = render(s["id"], calls, keys, cache, seg_dir)
        chars = sum(json.loads((cache / f"{k}.json").read_text())["usage_characters"] for k in keys)
        m = {"id": s["id"], "audio_ms": ms, "usage_characters": chars, "calls": keys}
        (seg_dir / f"{s['id']}.meta.json").write_text(json.dumps(m, ensure_ascii=False))
        manifest.append(m)
    timeline = [{k: s[k] for k in ("id", "gap_before", "scene") if k in s} | {"paras": s.get("paras", [])}
                for s in segs]
    (ep / "audio/timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=1))
    q1 = mm.quota()
    (ep / "audio/tts-manifest.json").write_text(json.dumps(
        {"mode": "drama", "segments": manifest, "usage_characters": sum(m["usage_characters"] for m in manifest),
         "billed_this_run": billed, "speech_ms": sum(m["audio_ms"] for m in manifest), "quota_before": q0,
         "quota_after": q1, "voice": vcfg, "cast": {r: list(v) for r, v in cast.items()},
         "level": {v.split("_")[-1]: round(g, 2) for v, g in gain.items()} if ref is not None else {}},   #
        ensure_ascii=False, indent=1))
    print(f"done: speech {sum(m['audio_ms'] for m in manifest) / 60000:.1f} min, billed this run {billed}; "
          f"quota after {q1}")


if __name__ == "__main__":
    try:
        main()
    except CastError as e:
        sys.exit(f"cast: {e}")
