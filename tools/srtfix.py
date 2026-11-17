#!/usr/bin/env python3
"""Clean subtitle cues (YouTube/Codex flagged cues that are only a closing 」 and cues whose end ≤ start —
45 of 78 episodes had them). A punctuation-only cue is glued onto the previous cue's text; a cue with no length
is dropped. Used by assemble.py for new builds and runnable over existing files.

Usage: srtfix.py FILE.srt [...] rewrite in place, print how many cues changed
"""
import re, sys

TEXT = re.compile(r"[0-9A-Za-z㐀-鿿]")


def clean(cues):
    out = []
    for a, b, c in cues:
        if not TEXT.search(c):                 # only punctuation (「」』。…) — belongs to the line before
            if out:
                pa, pb, pc = out[-1]
                out[-1] = (pa, max(pb, b), pc + c.strip())
            continue
        if b <= a:
            if out and out[-1][1] <= a:        # zero-length real text: give it a moment after the previous cue
                b = a + 0.5
            else:
                continue
        out.append((a, b, c))
    return out


def ts(x):
    return "%02d:%02d:%02d,%03d" % (lambda t: (t // 3600000, t // 60000 % 60, t // 1000 % 60, t % 1000))(round(x * 1000))


def parse(text):
    cues = []
    for blk in text.strip().split("\n\n"):
        L = blk.split("\n")
        if len(L) < 3:
            continue
        a, b = (sum(float(x) * m for x, m in zip(re.split("[:,]", s)[:3], (3600, 60, 1))) +
                int(re.split("[:,]", s)[3]) / 1000 for s in L[1].split(" --> "))
        cues.append((a, b, "\n".join(L[2:])))
    return cues


def render(cues):
    return "\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{c}\n" for i, (a, b, c) in enumerate(cues, 1))


def main():
    for f in sys.argv[1:]:
        before = parse(open(f, encoding="utf-8").read())
        after = clean(before)
        if len(after) != len(before) or after != before:
            open(f, "w", encoding="utf-8").write(render(after))
            print(f"{f}: {len(before)} → {len(after)} cues")


if __name__ == "__main__":
    main()
