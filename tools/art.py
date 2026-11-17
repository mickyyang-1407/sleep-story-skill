#!/usr/bin/env python3
"""Sleep-friendly frames: dim warm-sepia illustrations, title card, end card, thumbnail draft.

Usage: art.py <episode_dir>
"""
import json, sys
from pathlib import Path
import show
import season

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SUPP = "/System/Library/Fonts/Supplemental"
SONG = f"{SUPP}/Songti.ttc"            # 2 = Songti TC Bold, 7 = Songti TC Regular
BASK = f"{SUPP}/Baskerville.ttc"       # 2 = Italic
PING = __import__("os").environ.get("SD_FONT_PINGFANG") or next(
    (str(p) for p in Path("/System/Library/AssetsV2").glob("com_apple_MobileAsset_Font*/*.asset/AssetData/PingFang.ttc")),
    "/System/Library/Fonts/PingFang.ttc")  # 2 = TC Regular, 14 = TC Light

BG = (10, 8, 6)
W, H = 1920, 1080


def zh_num(n):
    d = "零一二三四五六七八九"
    if n < 10:
        return d[n]
    if n < 20:
        return "十" + (d[n % 10] if n % 10 else "")
    return d[n // 10] + "十" + (d[n % 10] if n % 10 else "")


def font(path, size, index):
    return ImageFont.truetype(path, size, index=index)


def vignette(w, h, edge=0.5):
    y, x = np.ogrid[-1:1:h * 1j, -1:1:w * 1j]
    r = np.sqrt((x * 0.9) ** 2 + y ** 2) / np.sqrt(0.81 + 1)
    return np.clip(1 - (1 - edge) * r ** 1.6, 0, 1)


def sepia(img, dark=(16, 12, 9), light=(122, 98, 72), gamma=1.1):
    v = (np.asarray(img.convert("L"), dtype=np.float32) / 255.0) ** gamma
    d, l = np.array(dark, np.float32), np.array(light, np.float32)
    return Image.fromarray((d + (l - d) * v[..., None]).astype(np.uint8), "RGB")


def tone(img, colour, light=(122, 98, 72)):
    """ anime90s seasons keep their colours , only dimmed for bedtime; the rest sepia."""
    if colour:
        return Image.fromarray((np.asarray(img.convert("RGB"), np.float32) * 0.82).astype(np.uint8), "RGB")
    return sepia(img, light=light)


def scene_frame(src, light=(122, 98, 72), colour=False):
    art = tone(Image.open(src), colour, light)
    art.thumbnail((W - 160, H - 120), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), BG)
    mask = Image.new("L", art.size, 0)
    ImageDraw.Draw(mask).rectangle([24, 24, art.size[0] - 24, art.size[1] - 24], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(18))
    canvas.paste(art, ((W - art.size[0]) // 2, (H - art.size[1]) // 2), mask)
    arr = np.asarray(canvas, np.float32) * vignette(W, H)[..., None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB")


def centered(draw, y, text, f, fill):
    w = draw.textlength(text, font=f)
    draw.text(((W - w) / 2, y), text, font=f, fill=fill)


def title_card(cfg):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    centered(d, 250, cfg["channel_working_name"], font(PING, 34, 14), (150, 132, 106))
    centered(d, 330, f"{cfg['series']}　第{zh_num(show.night(cfg))}夜",
             font(SONG, 46, 7), (182, 162, 132))
    centered(d, 410, cfg["title"], font(SONG, 150, 2), (214, 194, 160))
    centered(d, 610, cfg["title_en"], font(BASK, 40, 2), (150, 132, 106))
    centered(d, 960, f"旁白為 AI 語音合成｜故事改編自{cfg.get('author', '柯南·道爾')}公版原著｜{cfg.get('art_credit', '插畫：Sidney Paget（公版）')}",
             font(PING, 26, 2), (120, 106, 86))
    return im


def end_card(cfg):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    centered(d, 450, "晚安", font(SONG, 88, 7), (150, 132, 106))
    centered(d, 590, cfg["channel_working_name"], font(PING, 30, 14), (96, 84, 68))
    return im


def thumbnail(cfg, art_src):
    tw, th = 1280, 720
    im = Image.new("RGB", (tw, th), (20, 15, 11))
    art = (Image.open(art_src).convert("RGB") if season.of(cfg).get("art") == "anime90s"
           else sepia(Image.open(art_src), dark=(20, 15, 11), light=(222, 196, 152), gamma=1.0))
    art.thumbnail((620, 680), Image.LANCZOS)
    im.paste(art, (40, (th - art.size[1]) // 2))
    d = ImageDraw.Draw(im)
    x = 700
    d.text((x, 150), cfg["series"], font=font(SONG, 50, 7), fill=(214, 194, 160))
    d.text((x, 230), cfg["title"], font=font(SONG, 150, 2), fill=(240, 222, 186))
    d.text((x, 420), "大人的助眠推理故事", font=font(PING, 44, 2), fill=(200, 180, 146))
    d.text((x, 490), "慢慢聽，聽到睡著也沒關係", font=font(PING, 36, 14), fill=(170, 152, 124))
    return im


def main():
    ep = Path(sys.argv[1]).expanduser()
    cfg = json.loads((ep / "episode.json").read_text())
    out = ep / "art" / "frames"
    out.mkdir(parents=True, exist_ok=True)
    colour = season.of(cfg).get("art") == "anime90s"
    for name in sorted({s["art"] for s in cfg["scenes"] if s.get("art")}):
        scene_frame(ep / "art" / "paget" / name, colour=colour).save(out / f"scene-{name.split('-')[0]}.png")
    for c in cfg.get("art_cues", []):          # pictures that change at a paragraph (assemble.clips_for)
        scene_frame(ep / "art" / c["art"], colour=colour).save(out / f"cue-{Path(c['art']).stem}.png")
    title_card(cfg).save(out / "title.png")
    end_card(cfg).save(out / "end.png")
    thumb_src = cfg.get("thumbnail_art") or cfg["scenes"][0]["art"]
    thumbnail(cfg, ep / "art" / "paget" / thumb_src).save(ep / "art" / "thumbnail-draft.png")
    for p in sorted(out.glob("*.png")):
        a = np.asarray(Image.open(p).convert("L"), np.float32)
        print(f"{p.name}: mean luma {a.mean():.1f}/255, max {a.max():.0f}")


if __name__ == "__main__":
    main()
