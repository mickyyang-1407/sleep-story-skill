#!/usr/bin/env python3
"""Produce reviewed episodes end to end: art → narration → assembly → QC → upload text → cleanup.

Usage: produce.py <episode_dir> [...]
Narration shares MiniMax's general quota with the coding lanes: stop when the weekly remainder is below FLOOR.
"""
import contextlib, fcntl, json, os, subprocess, sys, time
from pathlib import Path

import mm

FLOOR = 20          # weekly % remaining that must stay for ccm3
# a one-off override the maintainer approves by name: SD_QUOTA_FLOOR=0 produce.py <ep>
FLOOR = int(os.environ.get("SD_QUOTA_FLOOR", FLOOR))
TOOLS = Path(__file__).resolve().parent


ASSEMBLERS = 5          # 3 → 5 for the music re-mix of 66 episodes next to the drama queues


@contextlib.contextmanager
def assembly_slot():
    while True:
        for k in range(ASSEMBLERS):
            f = open(TOOLS.parent / f".assemble.{k}.lock", "w")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                f.close(); continue
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN); f.close()
            return
        time.sleep(20)


def run(script, ep, *extra):
    subprocess.run([sys.executable, str(TOOLS / script), str(ep), *extra], check=True)


def main():
    for arg in sys.argv[1:]:
        ep = Path(arg).expanduser()
        cfg = json.loads((ep / "episode.json").read_text())
        # full radio drama: an episode with reviewed speaker tags is voiced by drama_tts.py;
        # single-voice narration, or drama narration older than its tags / casting, is redone (cached calls are free)
        drama = (ep / "script" / "speakers.json").exists()
        man = ep / "audio" / "tts-manifest.json"
        casting = [f for f in (ep / "script" / "speakers.json", ep / "script" / "cast.json",
                               TOOLS.parent / "cast-default.json") if f.exists()]
        redo = drama and not (man.exists() and json.loads(man.read_text()).get("mode") == "drama"
                              and man.stat().st_mtime > max(f.stat().st_mtime for f in casting))
        if cfg.get("status") not in ("reviewed", "narrated", "assembled", "qc-failed") and not redo:
            print(f"skip {ep.name}: status {cfg.get('status')}", flush=True); continue
        if not all("art" in s for s in cfg["scenes"]):
            run("fetch_art.py", ep)
        # art.py rewrites every frame; only redraw before narration so a re-assembly can keep its video
        if cfg.get("status") == "reviewed" or not (ep / "art" / "frames" / "title.png").exists():
            run("art.py", ep)
        if cfg.get("status") == "reviewed" or redo:
            q = mm.quota() if FLOOR > 0 else None   # [share export] no quota query when SD_QUOTA_FLOOR=0
            if q is not None and q["weekly"] < FLOOR:
                print(f"STOP {ep.name}: weekly quota {q['weekly']}% < floor {FLOOR}% (protecting ccm3)", flush=True)
                sys.exit(3)
            # one narrator at a time across processes: narration shares one per-minute request limit
            with open(TOOLS.parent / ".tts.lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                run("drama_tts.py" if drama else "tts.py", ep)
            cfg = json.loads((ep / "episode.json").read_text()); cfg["status"] = "narrated"
            (ep / "episode.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
        # thirteen episodes assembling at once pushed the load average past 500 and starved every
        # loudnorm pass; at most ASSEMBLERS episodes encode at a time, the rest wait their turn
        with assembly_slot():
            # re-runs after a QC/loudness fix: the picture only depends on the timeline and the frames
            video = ep / "build" / "video.mp4"
            fresh = video.exists() and video.stat().st_mtime > max(
                (ep / "audio" / "timeline.json").stat().st_mtime,
                *(f.stat().st_mtime for f in (ep / "art" / "frames").glob("*.png")))
            run("assemble.py", ep, *(["--reuse-video"] if fresh else []))
            run("qc.py", ep)
        run("package.py", ep)
        rep = json.loads((ep / "build" / "assemble-report.json").read_text())
        qc = json.loads((ep / "build" / "qc-report.json").read_text())
        ok = rep["aac"]["ok"] and all(r["ends_ok"] and r["asr_chars"] >= 0.9 * r["ref_chars"] for r in qc["sample"])
        for f in ("narration-44k.wav", "narration-48k.wav"):
            (ep / "build" / f).unlink(missing_ok=True)
        cfg = json.loads((ep / "episode.json").read_text())
        cfg["status"] = "produced" if ok else "qc-failed"
        (ep / "episode.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{ep.name}: {cfg['status']} | {rep['total_s'] / 60:.1f} min | AAC {rep['aac']} | "
              f"QC mean CER {qc['mean_cer']}", flush=True)


if __name__ == "__main__":
    main()
