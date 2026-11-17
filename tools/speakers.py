#!/usr/bin/env python3
"""Draft speaker tags for drama_tts.py, to be corrected by hand in the same pass as the script review.

Usage: speakers.py <episode_dir> [--alias 國王=king 陛下=king ...] [--write] [--from P001 --to P300]
Prints one line per paragraph that has top-level 「」: id, guessed speakers, and the text with each quote
numbered, so the review can fix the guesses in place. --write saves script/speakers.draft.json (never
speakers.json — that file is the reviewed truth).

Guess per quote: a speech verb (說 問 喊 …) right after or right before the quote, with the nearest known name
(福爾摩斯 → holmes, 我 → watson, plus --alias); otherwise alternate with the previous speaker in a dialogue;
otherwise "?".
"""
import json, re, sys
from pathlib import Path

from drama_tts import runs

VERB = r"(?:說|問|喊|叫|答|道|嚷|嘟囔|低聲|大聲|笑著|接著說|插嘴|回答|補充|繼續)"
BASE = {"福爾摩斯": "holmes", "我的朋友": "holmes", "我": "watson", "華生": "watson",
        "雷斯垂德": "lestrade", "葛雷格森": "gregson", "麥考夫": "mycroft", "哈德森太太": "hudson"}


def guess(text_before, text_after, alias):
    names = {**BASE, **alias}
    pat = "|".join(sorted(map(re.escape, names), key=len, reverse=True))
    m = re.match(rf"\s*[，,]?\s*({pat})[^「」。]{{0,8}}?{VERB}", text_after)
    if m:
        return names[m.group(1)]
    m = re.search(rf"({pat})[^「」。]{{0,10}}?{VERB}[^「」。]{{0,6}}[：:，,]?\s*$", text_before)
    if m:
        return names[m.group(1)]
    return None


def main():
    ep = Path(sys.argv[1]).expanduser()
    alias = {}
    if "--alias" in sys.argv:
        for a in sys.argv[sys.argv.index("--alias") + 1:]:
            if a.startswith("--"):
                break
            k, v = a.split("=")
            alias[k] = v
    rows = json.loads((ep / "script/script.json").read_text())
    ids = [r["id"] for r in rows]
    lo = ids.index(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 0
    hi = ids.index(sys.argv[sys.argv.index("--to") + 1]) + 1 if "--to" in sys.argv else len(rows)
    draft, prev, other = {}, None, None
    for r in rows[lo:hi]:
        rs = runs(r["zh"])
        if not any(k == "Q" for k, _ in rs):
            prev = other = None if len(r["zh"]) > 60 else prev   # long narration breaks a dialogue
            continue
        who, shown, n = [], [], 0
        for i, (k, t) in enumerate(rs):
            if k != "Q":
                shown.append(t); continue
            before = rs[i - 1][1] if i and rs[i - 1][0] == "N" else ""
            after = rs[i + 1][1] if i + 1 < len(rs) and rs[i + 1][0] == "N" else ""
            g = guess(before, after, alias) or (who[-1] if who else None)
            if g is None and prev and other:
                g = other                         # two-hander: the reply comes from the other one
            g = g or "?"
            who.append(g); n += 1
            shown.append(f"〔{n}〕「{t}」")
        if who[-1] != "?" and who[-1] != prev:
            other, prev = prev, who[-1]
        draft[r["id"]] = who[0] if len(set(who)) == 1 else who
        print(f"{r['id']} {str(who if len(set(who)) > 1 else who[0]):<12} {''.join(shown)}")
        if "--en" in sys.argv:
            print(f"     EN: {r.get('en', '')}")
    if "--write" in sys.argv:
        (ep / "script/speakers.draft.json").write_text(json.dumps(draft, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
