#!/usr/bin/env python3
"""Validate shorts/NN.json before rendering (the rules in shorts/SELECTING.md).

Usage: shorts_check.py [--draft] NN [NN ...] exit 1 and list every problem if any spec breaks a rule
 --draft reads shorts/drafts/NN.json (a v2 sample waiting for the maintainer; shorts.py --all never renders drafts)
 from night 103 on every spec must be format v2 (SELECTING.md §v2); 1–102 keep the old rules untouched.
"""
import json, re, sys
from pathlib import Path

from PIL import ImageFont
import season

ROOT = Path(__file__).resolve().parent.parent
BLACK = str(Path.home() / "Library/Fonts/NotoSansCJKtc-Black.otf")
CHANNEL = __import__("os").environ.get("SD_CHANNEL_URL", "https://www.youtube.com/@YOUR_CHANNEL")
MAX_STORY = 55.5                      # + 4 s end card ≤ 59.5 s
V2_FROM = 103                         # first night whose shorts are written in format v2
DRAFT = "--draft" in sys.argv
# a hook / question that only says "something is strange" gives the viewer nothing to hold on to
VAGUE = ("真相", "究竟", "離奇", "驚人", "不可思議", "震驚", "竟然是", "怎麼回事", "到底發生", "今天要說", "這是一宗", "一宗")
# the CTA / description must stay true whenever the short is watched: no airtime, no "already public"
DATED = ("今晚", "明晚", "今天", "明天", "今日", "已上線", "上線", "首播", "準時")
CLOCK = re.compile(r"\d+\s*[點点]|\d{1,2}[:：]\d{2}|(?:早上|上午|中午|下午|晚上|凌晨|夜裡)\s*[一二三四五六七八九十兩]+[點点]"
                   r"|[一二三四五六七八九十兩]+[點点](?:半|鐘|整)")         # 「一點也不」is not a time


def cues(ep):
    out = []
    for blk in (ep / "build" / "zh-Hant.srt").read_text().strip().split("\n\n"):
        L = blk.split("\n")
        t0, t1 = (sum(float(x) * m for x, m in zip(re.split("[:,]", s)[:3], (3600, 60, 1))) +
                  int(re.split("[:,]", s)[3]) / 1000 for s in L[1].split(" --> "))
        out.append((t0, t1, " ".join(L[2:])))
    return out


def check(n):
    errs = []
    ep = next((ROOT / "episodes").glob(f"{n:02d}-*"))
    cfg = json.loads((ep / "episode.json").read_text())
    specs = json.loads((ROOT / "shorts" / ("drafts" if DRAFT else "") / f"{n:02d}.json").read_text())
    cs = cues(ep)
    font = ImageFont.truetype(BLACK, 100)
    if [s.get("id") for s in specs] != ["a", "b", "c"]:
        errs.append("ids must be a, b, c in that order")
    if n >= V2_FROM:
        return errs + check_v2(n, cfg, specs, cs, font)
    for s in specs:
        tag = f"{n:02d}-{s.get('id')}"
        missing = [k for k in ("id", "kind", "start", "end", "hook", "art", "cta", "title", "desc") if k not in s]
        if missing:
            errs.append(f"{tag}: missing {', '.join(missing)}")
            continue
        a, b = s["start"], s["end"]
        if not (0 < a < b):
            errs.append(f"{tag}: start/end order")
        if b - a > MAX_STORY or b - a < 25:
            errs.append(f"{tag}: story part {b - a:.1f} s (25–{MAX_STORY} s)")
        if not any(abs(a - t0) <= 0.6 for t0, _, _ in cs):
            errs.append(f"{tag}: start {a} is not at a subtitle start (±0.6 s)")
        if not any(-0.2 <= b - t1 <= 0.8 for _, t1, _ in cs):
            errs.append(f"{tag}: end {b} is not just after a subtitle end (0–0.8 s)")
        rows = s["hook"].split("|")
        if len(rows) != 2 or any(font.getlength(r) > 960 for r in rows) or any(len(r) > 8 for r in rows):
            errs.append(f"{tag}: hook must be two lines of ≤ 8 characters: {s['hook']}")
        if s["art"] not in ("cover", "scene"):
            errs.append(f"{tag}: art must be cover or scene")
        if len(s["title"]) > 100 or f"〈{cfg['title']}〉" not in s["title"] or "#Shorts" not in s["title"]:
            errs.append(f"{tag}: title needs 〈{cfg['title']}〉 and #Shorts, ≤ 100 chars ({len(s['title'])})")
        head = s["desc"][:150]
        who = season.of(cfg)["who"]     # season 2; season 3
        if not all(k in head for k in (who, "睡前故事")) or CHANNEL not in s["desc"]:
            errs.append(f"{tag}: desc needs {who}＋睡前故事 in the first 150 chars and {CHANNEL}")
        if s["id"] == "c" and not s.get("ask"):
            errs.append(f"{tag}: the puzzle short needs an 'ask' line")
    return errs


def kept(cs, parts):
    """the story seconds shorts.py will keep (same trimming as shorts.plan)"""
    import shorts
    tot = 0.0
    for k, (pa, pb) in enumerate(parts):
        inside = [c for c in cs if c[1] > pa and c[0] < pb]
        cut = sum(nxt[0] - c[1] - shorts.TAIL - shorts.HEAD for c, nxt in zip(inside, inside[1:])
                  if nxt[0] - c[1] > shorts.TRIM_GAP)
        tot += pb - pa - cut + (shorts.PART_GAP if k < len(parts) - 1 else 0)
    return tot


def check_v2(n, cfg, specs, cs, font):
    errs, seen_parts, hooks, firsts = [], [], set(), set()
    who = season.of(cfg)["who"]
    for s in specs:
        tag = f"{n:02d}-{s.get('id')}"
        if s.get("v") != 2:
            errs.append(f"{tag}: from night {V2_FROM} on a spec must be \"v\": 2 (SELECTING.md §v2)")
            continue
        missing = [k for k in ("id", "kind", "parts", "hook", "question", "art", "cta", "title", "desc") if k not in s]
        if missing:
            errs.append(f"{tag}: missing {', '.join(missing)}")
            continue
        for k in ("start", "end", "ask"):
            if k in s:
                errs.append(f"{tag}: v2 has no '{k}' (parts / the question are the end card)")
        parts = s["parts"]
        if not (1 <= len(parts) <= 5) or any(len(p) != 2 or not 0 < p[0] < p[1] for p in parts):
            errs.append(f"{tag}: parts must be 1–5 [start, end] pairs")
            continue
        for i, (pa, pb) in enumerate(parts):
            if not any(-0.15 <= pa - t0 <= 0.1 for t0, _, _ in cs):     # no dead air before the first word
                errs.append(f"{tag}: part {i + 1} start {pa} is not at a subtitle start (−0.15…+0.1 s)")
            if not any(-0.05 <= pb - t1 <= 0.6 for _, t1, _ in cs):
                errs.append(f"{tag}: part {i + 1} end {pb} is not just after a subtitle end (0–0.6 s)")
            # 35 of 667 parts stopped mid-sentence (the next cue carried on with no pause, e.g. 「…姑媽過世的時候」)
            k = min(range(len(cs)), key=lambda j: abs(cs[j][1] - pb))
            if (k + 1 < len(cs) and cs[k + 1][0] - cs[k][1] < 0.05 and not re.search(r"[。？！…」』）]$", cs[k][2])
                    and not any(abs(qa - cs[k + 1][0]) < 0.1 for qa, _ in parts)):
                errs.append(f"{tag}: part {i + 1} stops mid-sentence 「{cs[k][2]}」 — end after 「{cs[k + 1][2]}」 or earlier")
            for qa, qb, other in seen_parts:
                if pa < qb and qa < pb:
                    errs.append(f"{tag}: part {i + 1} overlaps {other} — each short tells its own thing")
        seen_parts += [(pa, pb, f"{tag} part") for pa, pb in parts]
        for x, y in zip(parts, parts[1:]):
            if x[0] < y[1] and y[0] < x[1]:
                errs.append(f"{tag}: its own parts overlap")
        t = kept(cs, parts)
        if not 25 <= t <= MAX_STORY:
            errs.append(f"{tag}: story {t:.1f} s after trimming (25–{MAX_STORY} s)")
        first = next((c[2] for c in cs if abs(c[0] - parts[0][0]) <= 0.15), "")
        if first in firsts:
            errs.append(f"{tag}: opens on the same line as another short")
        firsts.add(first)
        rows = s["hook"].split("|")
        if len(rows) != 2 or any(font.getlength(r) > 960 for r in rows) or any(len(r) > 8 for r in rows):
            errs.append(f"{tag}: hook must be two lines of ≤ 8 characters: {s['hook']}")
        if s["hook"] in hooks:
            errs.append(f"{tag}: same hook as another short")
        hooks.add(s["hook"])
        q = s["question"]
        if not (q.endswith("？") and 4 <= len(q) <= 16):
            errs.append(f"{tag}: question must be one ≤ 16-character question ending in ？: {q}")
        for k in ("hook", "question"):
            bad = [w for w in VAGUE if w in s[k]]
            if bad:
                errs.append(f"{tag}: {k} says nothing concrete ({'、'.join(bad)}) — name the contradiction instead")
        cta = s["cta"]
        if "完整版" not in cta or len(cta) > 20 or "|" in cta:
            errs.append(f"{tag}: cta is one line ≤ 20 characters with 完整版: {cta}")
        for k in ("cta", "title", "desc"):
            bad = [w for w in DATED if w in s[k]] + CLOCK.findall(s[k])
            if bad:
                errs.append(f"{tag}: {k} promises a time or a public state ({'、'.join(bad)}) — keep it neutral")
        if s["art"] not in ("cover", "scene"):
            errs.append(f"{tag}: art must be cover or scene")
        if len(s["title"]) > 100 or f"〈{cfg['title']}〉" not in s["title"] or "#Shorts" not in s["title"]:
            errs.append(f"{tag}: title needs 〈{cfg['title']}〉 and #Shorts, ≤ 100 chars ({len(s['title'])})")
        if not all(k in s["desc"][:150] for k in (who, "睡前故事")) or CHANNEL not in s["desc"]:
            errs.append(f"{tag}: desc needs {who}＋睡前故事 in the first 150 chars and {CHANNEL}")
    return errs


def main():
    bad = 0
    for a in [x for x in sys.argv[1:] if not x.startswith("--")]:
        e = check(int(a))
        print(f"{int(a):02d}: " + ("OK" if not e else "\n  " + "\n  ".join(e)))
        bad += bool(e)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
