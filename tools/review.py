#!/usr/bin/env python3
"""Print an episode for human review: EN/ZH aligned per paragraph, M3 self-check flags inline, scene breaks marked.

Usage: review.py <episode_dir> [from_id] [to_id]
"""
import json, sys
from pathlib import Path


def main():
    ep = Path(sys.argv[1]).expanduser()
    rows = json.loads((ep / "script" / "script.json").read_text())
    cfg = json.loads((ep / "episode.json").read_text())
    flags = {}
    fp = ep / "script" / "flags.json"
    if fp.exists():
        for f in json.loads(fp.read_text()):
            flags.setdefault(f["id"], []).append(f)
    scenes = {s["start"]: s["chapter"] for s in cfg.get("scenes", [])}
    lo = sys.argv[2] if len(sys.argv) > 2 else rows[0]["id"]
    hi = sys.argv[3] if len(sys.argv) > 3 else rows[-1]["id"]
    print(f"# {cfg['number']} {cfg['title']}｜teaser: {cfg.get('teaser', '')}")
    for r in rows:
        if not lo <= r["id"] <= hi:
            continue
        if r["id"] in scenes:
            print(f"\n=== 場景：{scenes[r['id']]} ===")
        print(f"{r['id']} EN {r['en']}\n     ZH {r['zh']}")
        for f in flags.get(r["id"], []):
            print(f"     ⚑ {f.get('problem', '')}\n       → {f.get('fix', '')}")


if __name__ == "__main__":
    main()
