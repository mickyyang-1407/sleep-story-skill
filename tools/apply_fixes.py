#!/usr/bin/env python3
"""Apply reviewed corrections to an episode script, reproducibly.

Usage: apply_fixes.py <episode_dir> <fixes.json>
fixes.json: [{"id": "P012", "zh": "整段新譯文"} | {"id": "P012", "old": "舊字串", "new": "新字串"}]
Each "old" must occur exactly once in its paragraph, or nothing is written.
The raw M3 text stays in zh_raw; every applied fix is recorded in script/fixes-applied.json.
"""
import json, re, sys
from pathlib import Path


def main():
    ep, fixes_path = Path(sys.argv[1]).expanduser(), Path(sys.argv[2]).expanduser()
    sp = ep / "script" / "script.json"
    rows = json.loads(sp.read_text())
    by = {r["id"]: r for r in rows}
    fixes = json.loads(fixes_path.read_text())
    bad = []
    for f in fixes:
        r = by.get(f["id"])
        if r is None:
            bad.append((f["id"], "no such paragraph")); continue
        if "zh" in f:
            r["zh"] = f["zh"]
        else:
            n = r["zh"].count(f["old"])
            if n != 1:
                bad.append((f["id"], f"old occurs {n}×: {f['old'][:30]}")); continue
            r["zh"] = r["zh"].replace(f["old"], f["new"])
        r["edited"] = True
    if bad:
        raise SystemExit(f"not applied, fix these first: {bad}")
    allzh = "\n".join(r["zh"] for r in rows)
    problems = []
    if "！" in allzh or "!" in allzh:
        problems.append("exclamation mark")
    if allzh.count("「") != allzh.count("」") and not any(r["zh"].startswith("「") and "」" not in r["zh"] for r in rows):
        problems.append("unbalanced 「」")
    if allzh.count("『") != allzh.count("』"):
        problems.append("unbalanced 『』")
    if re.search(r"[0-9]", allzh):
        problems.append("arabic digits: " + ",".join(sorted(set(re.findall(r"[0-9]+", allzh)))[:5]))
    sp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (ep / "script" / "script-zh.md").write_text("\n\n".join(f"【{r['id']}】{r['zh']}" for r in rows) + "\n",
                                                encoding="utf-8")
    log = ep / "script" / "fixes-applied.json"
    prev = json.loads(log.read_text()) if log.exists() else []
    log.write_text(json.dumps(prev + fixes, ensure_ascii=False, indent=1), encoding="utf-8")
    cfg_p = ep / "episode.json"
    cfg = json.loads(cfg_p.read_text())
    # a late punctuation fix on an already narrated episode must not send it back to "reviewed"
    # (produce.py would then re-narrate it)
    if cfg.get("status") in (None, "extracted", "translated", "translated-incomplete", "reviewed"):
        cfg["status"] = "reviewed"
    cfg_p.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"applied {len(fixes)} fixes to {len({f['id'] for f in fixes})} paragraphs; warnings: {problems or 'none'}")


if __name__ == "__main__":
    main()
