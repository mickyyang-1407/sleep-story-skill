#!/usr/bin/env python3
"""Two deliveries of every episode — where each one lives and whether it is current.

 music NN-…-preview.mp4 · build/assemble-report.json · 完成影片/ · 完成Shorts/ · shorts/out/
 nomusic NN-…-nomusic.mp4 · build/assemble-report-nomusic.json · 完成影片-無配樂/ · 完成Shorts-無配樂/ · shorts/out-nomusic/
The shell/env default is SD_VARIANT (music when unset).
"""
import json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VARIANTS = ("music", "nomusic")
CURRENT = os.environ.get("SD_VARIANT", "music")
assert CURRENT in VARIANTS, f"SD_VARIANT must be one of {VARIANTS}"


def paths(v=None):
    v = v or CURRENT
    nm = v == "nomusic"
    return {"variant": v, "suffix": "nomusic" if nm else "preview",
            "report": "assemble-report-nomusic.json" if nm else "assemble-report.json",
            "long_dir": ROOT / ("完成影片-無配樂" if nm else "完成影片"),
            "shorts_dir": ROOT / ("完成Shorts-無配樂" if nm else "完成Shorts"),
            "shorts_out": ROOT / "shorts" / ("out-nomusic" if nm else "out")}


def current(ep, v=None):
    """True when the episode's delivery for this variant was built with today's settings: the no-music cut just has to
 pass loudness; the music cut must carry the pool bed this episode rotates to, at today's level and ducking
 (so an episode still carrying the broken ACE-Step bed never counts)."""
    p = paths(v)
    rep = ep / "build" / p["report"]
    if not rep.exists() or json.loads((ep / "episode.json").read_text()).get("status") != "produced":
        return False
    r = json.loads(rep.read_text())
    if not r.get("aac", {}).get("ok"):
        return False
    if not leveled(ep) or rep.stat().st_mtime < (ep / "audio" / "tts-manifest.json").stat().st_mtime:
        return False
    if p["variant"] == "nomusic":
        return True
    from assemble import bed_for, music_settings
    m = r.get("music", {})
    n = json.loads((ep / "episode.json").read_text())["number"]
    return bool(m.get("on")) and m.get("bed") == bed_for(n).name and all(m.get(k) == x for k, x in music_settings().items())


def leveled(ep):
    """the drama narration was rendered with every voice matched to the narrator
 (drama_tts.py writes "level" into tts-manifest.json; the Rampo season had it from before the key existed)."""
    man = ep / "audio" / "tts-manifest.json"
    if not man.exists():
        return False
    m = json.loads(man.read_text())
    return m.get("mode") != "drama" or "level" in m or \
        json.loads((ep / "episode.json").read_text()).get("author") == "江戶川亂步"
