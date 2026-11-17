"""Review-fix builder: write fixes-review.json from a Python session instead of by hand.

 import sys; sys.path.insert(0, "../../tools"); from fixkit import FK, nest
 k = FK("."); k.e("P012", "舊", "新"); k.z("P013", "整段"); k.g("馬房", "馬廄") # g = every paragraph
 nest(k) # rebuild 「」/『』 levels from the EN typography (see nest.__doc__)
 k.unclose_auto # multi-paragraph speech: only the last paragraph closes
 k.quotes; k.save # then: python3 apply_fixes.py <ep> <ep>/script/fixes-review.json

Every e is checked against the text as already edited, so a fix list never fails half-way in apply_fixes.
nest rules were checked on episodes 02–12 (dry run): it must not touch paragraphs whose ZH moved the
attribution (「…？』我問。) and must not close an inner quote that runs on into the next paragraph (letters)."""
import json, sys
class FK:
    def __init__(s, ep):
        s.ep = ep; s.cur = {r['id']: r['zh'] for r in json.load(open(f'{ep}/script/script.json'))}
        s.en = {r['id']: r['en'] for r in json.load(open(f'{ep}/script/script.json'))}; s.F = []
    def e(s, i, o, n):
        c = s.cur[i].count(o)
        if c != 1: raise SystemExit(f'{i}: {o!r} occurs {c}x')
        s.cur[i] = s.cur[i].replace(o, n); s.F.append({"id": i, "old": o, "new": n})
    def z(s, i, t): s.cur[i] = t; s.F.append({"id": i, "zh": t})
    def g(s, o, n):
        for i, t in s.cur.items():
            if o in t:
                if t.count(o) == 1: s.e(i, o, n)
                else: s.z(i, t.replace(o, n))
    def unclose_auto(s):
        for i, t in list(s.cur.items()):
            en = s.en[i].strip()
            if en.startswith('“') and en.count('“') > en.count('”') and t.startswith('「') and t.endswith('」') and t.count('「') == 1:
                s.unclose(i)

    def unclose(s, *ids):
        for i in ids:
            t = s.cur[i]
            if not t.endswith('」'): raise SystemExit(f'{i} not closed')
            s.z(i, t[:-1])
    def save(s):
        json.dump(s.F, open(f'{s.ep}/script/fixes-review.json', 'w'), ensure_ascii=False, indent=1); print(len(s.F), 'fixes')
    def quotes(s):
        for i, t in s.cur.items():
            en = s.en[i].strip()
            if en.startswith('“') and not en.endswith('”') and t.endswith('」'): print('Q open-continue but closed', i)
            if en.startswith('“') and '「' not in t: print('Q missing', i)

def nest(k, verbose=True):
    """Rebuild quote levels from the EN typography.
 “‘ paragraphs are inner dialogue inside an outer narration quote: outer 「, inner 『』.
 “ paragraphs whose ZH carries no bracket at all lost their outer 「.
 Then fix closings: outer 」 only when EN ends with ”; inner 』 when EN ends with ’."""
    import re
    for i, t in list(k.cur.items()):
        en = k.en[i].strip()
        cont = en.count('“') > en.count('”')   # outer quote still open at paragraph end (“…,” he said. is closed)
        if en.startswith('“‘'):
            body = t.lstrip('「『').rstrip('」』')
            body = body.replace('「', '『').replace('」', '』')
            m = re.search('[『』]', body)
            pre = '「' if (m and m.group() == '『') else '「『'
            br = re.findall('[『』]', body)
            # re-close the inner quote only when the ZH body still has one open (it may end in narration: 「『…？』我問。)
            # …but not when the EN inner quote runs on into the next paragraph (letters, long reports): no closing ’ at all
            # the LAST quote mark decides: …,’ said she; ‘but … (runs on) must not be closed here.
            # ” counts too (a third-level quote closes with it); apostrophes (don’t) are skipped by the
            # punctuation-before / space-before patterns
            marks = [(m.end(), "close") for m in re.finditer(r"[.,!?;:—-][’”]", en)] + \
                    [(m.end(), "open") for m in re.finditer(r"(?:^|\s)[‘“]", en)]
            closes = bool(marks) and max(marks)[1] == "close"
            post = ('』' if (closes and (not br or br[-1] == '『')) else '') + ('' if cont else '」')
            new = pre + body + post
        elif en.startswith('“') and '「' not in t and '『' not in t:
            new = '「' + t.rstrip('」') + ('' if cont else '」')
        else:
            new = t
            if en.startswith('“') and cont and t.startswith('「') and t.endswith('」') and t.count('「') == 1:
                new = t[:-1]
        if new != t:
            k.z(i, new)
            if verbose: print('nest', i, new[:18], '…', new[-12:])
