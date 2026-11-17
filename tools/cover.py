#!/usr/bin/env python3
"""YouTube thumbnail: the painted cover (covers/NN.png, text-free, left ~35% kept as plain umber) + series label,
episode title and a one-line hook, all in the left panel..

Usage: cover.py 1 2 … 10 → covers/final/NN.jpg (1920×1080, < 2 MB, YouTube's thumbnail limit)
Hooks live in covers/hooks.json ({"1": "抄百科全書，週薪四英鎊？", …}); keep them short and spoiler-free.
"""
import os
import json, sys
from pathlib import Path
import show, season

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from art import zh_num, SONG

ROOT = Path(__file__).resolve().parent.parent
COV = ROOT / "covers"
BLACK = os.environ.get("SD_FONT_NOTO_BLACK", str(Path.home() / "Library/Fonts/NotoSansCJKtc-Black.otf"))
BOLD = os.environ.get("SD_FONT_NOTO_BOLD", str(Path.home() / "Library/Fonts/NotoSansCJKtc-Bold.otf"))
W, H = 1920, 1080
X0, XMAX = 72, 640                 # text column inside the plain panel
CREAM, GOLD, INK = (250, 238, 214), (232, 184, 96), (26, 14, 6)


def fit(text, path, size, width, index=0):
    while size > 20:
        f = ImageFont.truetype(path, size, index=index)
        if f.getlength(text) <= width:
            return f
        size -= 4
    return ImageFont.truetype(path, size, index=index)


def lines_for(title):
    """One line up to 5 characters; longer titles break into two balanced lines (博斯科姆／溪谷之謎)."""
    if len(title) <= 5:
        return [title]
    k = (len(title) + 1) // 2
    return [title[:k], title[k:]]


def draw_text(img, xy, text, f, fill, stroke, shadow=10):
    """Stroked text with a soft drop shadow so it holds at phone-thumbnail size on any panel shade."""
    sh = Image.new("L", img.size, 0)
    ImageDraw.Draw(sh).text((xy[0] + 6, xy[1] + 8), text, font=f, fill=200, stroke_width=stroke)
    sh = sh.filter(ImageFilter.GaussianBlur(shadow))
    img.paste(Image.new("RGB", img.size, (0, 0, 0)), (0, 0), sh)
    ImageDraw.Draw(img).text(xy, text, font=f, fill=fill, stroke_width=stroke, stroke_fill=INK)


def make(n, hooks, breaks):
    ep = next((ROOT / "episodes").glob(f"{n:02d}-*"))
    cfg = json.loads((ep / "episode.json").read_text())
    img = Image.open(COV / f"{n:02d}.png").convert("RGB").resize((W, H), Image.LANCZOS)
    # a gentle darkening behind the column so cream text never sits on a light brush stroke
    shade = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shade).rectangle((0, 0, XMAX + 40, H), fill=70)
    shade = shade.filter(ImageFilter.GaussianBlur(60))
    img.paste(Image.new("RGB", (W, H), (20, 10, 4)), (0, 0), shade)

    width = XMAX - X0
    lab_text = f"福爾摩斯睡前故事｜第{zh_num(cfg['number'])}夜"
    label = fit(lab_text, SONG, 46, width, index=2)
    brk = breaks.get(str(n))            # covers/hooks.json "breaks": {"2": "波希米亞|醜聞"} when the halves split a name
    rows = brk.split("|") if brk else lines_for(cfg["title"])
    size = min(fit(r, SONG, 250 if len(rows) == 1 else 170, width, index=2).size for r in rows)
    tf = ImageFont.truetype(SONG, size, index=2)
    hook = hooks.get(str(n), "")
    hf = fit(hook, BLACK, 66, width) if hook else None
    # stack: label, title rows, rule, hook — centred in the space above the badge
    block = 46 + 44 + int(size * 1.12) * len(rows) + 44 + 6 + 40 + (hf.size if hf else 0)
    y = max(90, (H - 170 - block) // 2)
    draw_text(img, (X0, y), lab_text, label, GOLD, 2, 6)
    y += 46 + 44
    for r in rows:
        draw_text(img, (X0 - 6, y), r, tf, CREAM, 8, 14)
        y += int(size * 1.12)
    y += 44
    ImageDraw.Draw(img).rectangle((X0, y, X0 + 120, y + 6), fill=GOLD)
    y += 6 + 40
    if hf:
        draw_text(img, (X0, y), hook, hf, GOLD, 4, 8)
    badge = "廣播劇完整版・助眠"
    bf = ImageFont.truetype(BOLD, 36)
    bw = int(bf.getlength(badge))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((X0, H - 150, X0 + bw + 44, H - 150 + 64), radius=12, fill=(150, 40, 28))
    d.text((X0 + 22, H - 150 + 10), badge, font=bf, fill=CREAM)

    out = COV / "final" / f"{n:02d}.jpg"
    out.parent.mkdir(exist_ok=True)
    for q in (92, 88, 84, 80):
        img.save(out, quality=q, optimize=True, progressive=True)
        if out.stat().st_size < 2_000_000:
            break
    return out


YELLOW, RED = (255, 214, 0), (196, 30, 30)
GRADE = "night"
MOON_GAP = 36                           # "boost" for muted art (v3.1), "night" for loud art (v4)


def make_bold(n, big):
    """v2 after a look at the genre's search results: at phone size (~320 px wide) only the title survived,
 the hook/label/badge turned to mush, and all ten looked the same brown. So: the hook becomes the headline
 (two short lines, heavy sans, yellow/white with a thick black stroke), the title moves into a red tag with the
 night number, the picture gets more colour and contrast, and nothing else competes."""
    from PIL import ImageEnhance
    ep = next((ROOT / "episodes").glob(f"{n:02d}-*"))
    cfg = json.loads((ep / "episode.json").read_text())
    img = Image.open(COV / f"{n:02d}.png").convert("RGB").resize((W, H), Image.LANCZOS)
    if GRADE == "boost":                       # v3.1 art was muted: push colour and contrast
        img = ImageEnhance.Color(img).enhance(1.35)
        img = ImageEnhance.Contrast(img).enhance(1.18)
    else:                                      # v4 art is already loud: pull it toward night, keep the drama
        img = ImageEnhance.Color(img).enhance(0.82)
        img = ImageEnhance.Brightness(img).enhance(0.86)
        vig = Image.new("L", (W, H), 0)
        ImageDraw.Draw(vig).ellipse((-W * 0.15, -H * 0.35, W * 1.15, H * 1.35), fill=255)
        vig = vig.filter(ImageFilter.GaussianBlur(160))
        night = Image.new("RGB", (W, H), (6, 10, 28))
        img = Image.composite(img, night, vig.point(lambda v: 90 + v * 165 // 255))
    shade = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shade).rectangle((0, 0, 760, H), fill=120)
    shade = shade.filter(ImageFilter.GaussianBlur(90))
    img.paste(Image.new("RGB", (W, H), (8, 4, 2)), (0, 0), shade)

    # every line centred on one axis , placed by its ink box, not by the font's
    # advance/ascent, so a line of 4 and a line of 5 characters share the same visual centre
    cx, width = 460, 800
    rows = big[str(n)].split("|")
    size = min(fit(r, BLACK, 190, width).size for r in rows)
    f = ImageFont.truetype(BLACK, size)
    tag = f"{season.of(cfg)['label']}第{show.night(cfg)}夜｜{cfg['title']}"   # tell the seasons apart
    # Long serialized titles must stay inside the 920 px left panel.
    tf = fit(tag, BLACK, 64, 760)
    tag_h, gap, line_h = 104, 44, int(size * 1.12)
    y = (H - (tag_h + gap + line_h * len(rows) + MOON_GAP + 64)) // 2
    d = ImageDraw.Draw(img)
    l, t, r_, b = d.textbbox((0, 0), tag, font=tf)
    tw = r_ - l
    d.rounded_rectangle((cx - tw // 2 - 28, y, cx + tw // 2 + 28, y + tag_h), radius=14, fill=RED)
    d.text((cx - tw // 2 - l, y + (tag_h - (b - t)) // 2 - t), tag, font=tf, fill=(255, 255, 255))
    y += tag_h + gap
    for i, r in enumerate(rows):
        l, t, r_, b = d.textbbox((0, 0), r, font=f)
        draw_text(img, (cx - (r_ - l) // 2 - l, y - t + (line_h - (b - t)) // 2), r, f,
                  YELLOW if i == len(rows) - 1 else (255, 255, 255), 14, 16)
        y += line_h
    # sleep cue: a crescent moon + 助眠 under the hook, so the loud picture still
    # tells a phone-sized glance what kind of video this is
    y += MOON_GAP
    mf = ImageFont.truetype(BLACK, 54)
    word = "助眠廣播劇"
    ww = int(mf.getlength(word))
    r = 27
    x0 = cx - (2 * r + 18 + ww) // 2
    moon = Image.new("L", (2 * r + 4, 2 * r + 4), 0)       # crescent = disc minus an offset disc
    md = ImageDraw.Draw(moon)
    md.ellipse((2, 2, 2 + 2 * r, 2 + 2 * r), fill=255)
    md.ellipse((2 + int(r * 0.62), 2 - int(r * 0.28), 2 + int(r * 0.62) + 2 * r, 2 - int(r * 0.28) + 2 * r), fill=0)
    img.paste(Image.new("RGB", moon.size, (255, 226, 150)), (x0, y + 6), moon)
    draw_text(img, (x0 + 2 * r + 18, y - 4), word, mf, (255, 226, 150), 6, 8)
    out = COV / "final" / f"{n:02d}.jpg"
    out.parent.mkdir(exist_ok=True)
    for q in (92, 88, 84, 80):
        img.save(out, quality=q, optimize=True, progressive=True)
        if out.stat().st_size < 2_000_000:
            break
    return out


def main():
    data = json.loads((COV / "hooks.json").read_text()) if (COV / "hooks.json").exists() else {}
    breaks, big = data.pop("breaks", {}), data.pop("big", {})
    classic = "--classic" in sys.argv          # the v1 layout: series label + big title + small hook
    for a in (a for a in sys.argv[1:] if not a.startswith("--")):
        o = make(int(a), data, breaks) if classic or a not in big else make_bold(int(a), big)
        print(o.name, f"{o.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
