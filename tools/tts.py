#!/usr/bin/env python3
"""Synthesize an episode's narration with MiniMax T2A in scene-aligned blocks (resumable, parallel).

Usage: tts.py <episode_dir> [--redo B007 ...]
Reads script/script.json and episode.json (voice, intro, outro, gaps, scenes)
Writes audio/seg/{INTRO,Bnnn,OUTRO}.{wav,sub.json,meta.json}, audio/timeline.json, audio/tts-manifest.json

A block is consecutive paragraphs of one scene, up to ~1,500 characters, with the paragraph pause written
into the text; ~15 requests per episode instead of one per paragraph keeps us under the per-minute limit.
"""
import json, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import mm

BLOCK_CHARS = 1500


def paced(text):
    # breathing room after each sentence, inside a paragraph (not at its end)
    text = re.sub(r"([。？])(?![」』]|$)", r"\1<#0.5#>", text)
    return re.sub(r"([。？][」』])(?!$)", r"\1<#0.4#>", text)


def plan(cfg, rows):
    g = cfg["gaps"]
    by = {r["id"]: r["zh"] for r in rows}
    starts = {s["start"]: i for i, s in enumerate(cfg["scenes"])}
    blocks, cur, n, scene = [], None, 0, 0
    for r in rows:
        new_scene = r["id"] in starts and r["id"] != rows[0]["id"]
        if r["id"] in starts:
            scene = starts[r["id"]]
        if cur and (new_scene or n + len(r["zh"]) > BLOCK_CHARS):
            blocks.append(cur); cur, n = None, 0
        if cur is None:
            cur = {"id": f"B{len(blocks) + 1:03d}", "scene": scene, "paras": []}
        cur["paras"].append(r["id"]); n += len(r["zh"])
    blocks.append(cur)
    segs = [{"id": "INTRO", "gap_before": 2.0, "scene": None, "tts": cfg["intro"]}]
    prev = None
    for b in blocks:
        gap = g["after_intro_s"] if prev is None else (g["scene_s"] if b["scene"] != prev else g["paragraph_s"])
        segs.append({**b, "gap_before": gap, "tts": f"<#{g['paragraph_s']}#>".join(paced(by[p]) for p in b["paras"])})
        prev = b["scene"]
    segs.append({"id": "OUTRO", "gap_before": g["before_outro_s"], "scene": None, "tts": cfg["outro"]})
    return segs


def synth(seg, cfg, outdir):
    wav, sub, meta = (outdir / f"{seg['id']}{ext}" for ext in (".wav", ".sub.json", ".meta.json"))
    if wav.exists() and sub.exists() and meta.exists() and json.loads(meta.read_text()).get("tts") == seg["tts"]:
        return json.loads(meta.read_text())
    v = cfg["voice"]
    for attempt in range(8):
        r = mm.call("POST", f"{mm.HOST}/v1/t2a_v2", {
            "model": v["model"], "text": seg["tts"], "stream": False, "output_format": "url",
            "language_boost": "Chinese",
            "voice_setting": {"voice_id": v["voice_id"], "speed": v["speed"], "vol": 1, "pitch": v["pitch"],
                              "emotion": v["emotion"]},
            "audio_setting": {"sample_rate": 44100, "format": "wav", "channel": 1},
            "pronunciation_dict": {"tone": v["pronunciation"]},
            "subtitle_enable": True, "subtitle_type": "sentence"}, timeout=240)  # a normal block returns in <15 s; 900 s stalled every queued episode on
        br = r.get("base_resp", {})
        # per-minute limits arrive as HTTP 200 with these codes: 1002 = RPM, 1039 = TPM (seen with 3 episodes queued)
        if br.get("status_code") in (1002, 1039):
            print(f"  {seg['id']}: rate limited, retry {attempt + 1}", flush=True)
            time.sleep(min(60, 5 * 2 ** attempt))
            continue
        break
    data = r.get("data") or {}
    if br.get("status_code") != 0 or not data.get("audio"):
        raise RuntimeError(f"{seg['id']}: {br}")
    wav.write_bytes(mm.fetch_bytes(data["audio"], timeout=300))
    sub.write_bytes(mm.fetch_bytes(data["subtitle_file"]))
    ex = r["extra_info"]
    m = {"id": seg["id"], "audio_ms": ex["audio_length"], "usage_characters": ex["usage_characters"], "tts": seg["tts"]}
    meta.write_text(json.dumps(m, ensure_ascii=False))
    return m


def main():
    ep = Path(sys.argv[1]).expanduser()
    cfg = json.loads((ep / "episode.json").read_text())
    rows = json.loads((ep / "script" / "script.json").read_text())
    outdir = ep / "audio" / "seg"
    outdir.mkdir(parents=True, exist_ok=True)
    segs = plan(cfg, rows)
    if "--redo" in sys.argv:
        for sid in sys.argv[sys.argv.index("--redo") + 1:]:
            for f in outdir.glob(f"{sid}.*"):
                f.unlink()
    q0 = mm.quota()
    print(f"{len(segs)} segments ({len(segs) - 2} blocks); quota before {q0}", flush=True)
    t0, results = time.time(), {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = {pool.submit(synth, s, cfg, outdir): s["id"] for s in segs}
        for k, f in enumerate(as_completed(futs), 1):
            results[futs[f]] = f.result()
            print(f"  {k}/{len(segs)} {futs[f]} in {time.time() - t0:.0f}s", flush=True)
    timeline = [{k: s[k] for k in ("id", "gap_before", "scene") if k in s} | {"paras": s.get("paras", [])}
                for s in segs]
    (ep / "audio" / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=1))
    manifest = [{k: v for k, v in results[s["id"]].items() if k != "tts"} for s in segs]
    q1 = mm.quota()
    (ep / "audio" / "tts-manifest.json").write_text(json.dumps(
        {"segments": manifest, "usage_characters": sum(m["usage_characters"] for m in manifest),
         "speech_ms": sum(m["audio_ms"] for m in manifest), "quota_before": q0, "quota_after": q1,
         "voice": cfg["voice"]}, ensure_ascii=False, indent=1))
    print(f"done: speech {sum(m['audio_ms'] for m in manifest) / 60000:.1f} min, billed characters "
          f"{sum(m['usage_characters'] for m in manifest)}; quota after {q1}")


if __name__ == "__main__":
    main()
