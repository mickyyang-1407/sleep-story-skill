#!/usr/bin/env python3
"""Drop extraction residue from the end of an episode script .

The Case-Book source (episodes 45–56) was split on the story headings, so every story's last paragraph is the next
story's Roman numeral ("II", "IV", …) — M3 translated it to 「四」「完」「第八案」 and the narrator would read it out.
Episode 56 (the book's last story) also carries the publisher's back matter from "Printed in Great Britain" on.

Usage: trim_tail.py <episode_dir> [--dry-run]
Removes trailing rows whose EN is a bare Roman numeral, and everything from a "Printed in Great Britain" row on;
refuses if scenes or speakers.json point at a removed row. Rewrites script.json and script-zh.md. Idempotent."""
import json, re, sys
from pathlib import Path

ROMAN = re.compile(r"^[IVXLC]+\.?$")


def main():
    ep = Path(sys.argv[1]).expanduser()
    sp = ep / "script" / "script.json"
    rows = json.loads(sp.read_text())
    cut = len(rows)
    for i, r in enumerate(rows):
        if r["en"].strip().startswith("Printed in Great Britain"):
            cut = i
            break
    while cut and ROMAN.match(rows[cut - 1]["en"].strip()):
        cut -= 1
    gone = [r["id"] for r in rows[cut:]]
    if not gone:
        print(f"{ep.name}: nothing to trim"); return
    cfg = json.loads((ep / "episode.json").read_text())
    tags_p = ep / "script" / "speakers.json"
    tags = json.loads(tags_p.read_text()) if tags_p.exists() else {}
    bad = [s["start"] for s in cfg.get("scenes", []) if s["start"] in gone] + [k for k in tags if k in gone]
    if bad:
        raise SystemExit(f"{ep.name}: scenes/speakers point at rows to be removed: {bad}")
    print(f"{ep.name}: remove {gone} = {[r['en'][:30] for r in rows[cut:]]}")
    if "--dry-run" in sys.argv:
        return
    rows = rows[:cut]
    sp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (ep / "script" / "script-zh.md").write_text("\n\n".join(f"【{r['id']}】{r['zh']}" for r in rows) + "\n",
                                                  encoding="utf-8")


if __name__ == "__main__":
    main()
