#!/usr/bin/env python3
"""YouTube Shorts (9:16) from a finished episode — three per episode: opening hook, mid-story turn, open puzzle
. Everything comes from the episode we already made: the mixed audio
(voices + music bed), the Traditional-Chinese subtitles, the cover and scene illustrations.

Usage: shorts.py <NN> [id ...] | shorts.py --all (every spec whose episode is mixed and whose shorts are stale)
Reads shorts/NN.json: [{"id": "a", "kind": "懸念", "start": 548.0, "end": 603.0, "hook": "只要紅頭髮|週薪四英鎊？",
 "art": "cover" | "scene", "cta": "今晚 10 點｜完整版廣播劇", "title": "...", "desc": "..."}]
Writes shorts/out/NN-<id>.mp4 (1080×1920, 30 fps, ≤ 60 s, −14 LUFS) and NN-<id>.txt (title + description)

This ffmpeg has no drawtext/subtitles filters, so every piece of text is a transparent PNG drawn with PIL and
laid on with overlay=enable='between(t,a,b)'. Layout keeps clear of the Shorts UI: nothing important in the
bottom 420 px (title, channel, music row) or the right 140 px (like / comment / share column).

format v2 ("v": 2 — every short from night 103 on; specs without it render exactly as before, so the published
1–102 never change on a re-render): "parts": [[start, end], …] instead of start/end — the first part is the anomaly,
later parts only the background it needs; pauses longer than 0.7 s inside a part are cut down to ~0.45 s; subtitles
come one short line at a time; the end card is the spec's "question" + one neutral "cta" (no date, no "已上線",
no channel-search line, no "ask"); a zh-Hans.srt is written next to the zh-Hant one (Bilibili).
"""
import os
import json, re, subprocess, sys
from pathlib import Path
import show

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
import variant
VAR = variant.paths()           # SD_VARIANT=nomusic → cut from the no-music long video into 完成Shorts-無配樂/
BLACK = os.environ.get("SD_FONT_NOTO_BLACK", str(Path.home() / "Library/Fonts/NotoSansCJKtc-Black.otf"))
BOLD = os.environ.get("SD_FONT_NOTO_BOLD", str(Path.home() / "Library/Fonts/NotoSansCJKtc-Bold.otf"))
W, H, FPS = 1080, 1920, 30
ART_Y, ART_H = 590, 730                    # illustration band: centre 1600×1080 of the art, scaled to 1080 wide
SUB_Y = 1360                               # subtitle baseline area (above the Shorts caption block)
CARD_S = 4.0                               # end card seconds
YELLOW, RED, CREAM = (255, 214, 0), (196, 30, 30), (255, 240, 214)


def srt_cues(path, a, b):
    out = []
    for blk in path.read_text().strip().split("\n\n"):
        L = blk.split("\n")
        if len(L) < 3:
            continue
        t0, t1 = (sum(float(x) * m for x, m in zip(re.split("[:,]", s)[:3], (3600, 60, 1))) +
                  int(re.split("[:,]", s)[3]) / 1000 for s in L[1].split(" --> "))
        if t1 > a and t0 < b:
            out.append((max(t0, a) - a, min(t1, b) - a, " ".join(L[2:])))
    return out


TRIM_GAP, TAIL, HEAD = 0.70, 0.20, 0.25    # v2: a pause > 0.7 s inside a part keeps 0.2 s after + 0.25 s before
PART_GAP = 0.30                            # v2: a breath of silence between two parts
SUB_CHARS = 13                             # v2: one subtitle line, ≤ 13 characters, at 68 px


def plan(ep, spec):
    """v2: the source intervals actually kept, as [src_start, src_end, silence_after]."""
    cs = srt_cues(ep / "build" / "zh-Hant.srt", 0, 1e9)
    out, parts = [], spec["parts"]
    for k, (pa, pb) in enumerate(parts):
        inside = [c for c in cs if c[1] > pa and c[0] < pb]
        s = pa
        for c, nxt in zip(inside, inside[1:]):
            if nxt[0] - c[1] > TRIM_GAP:
                out.append([s, c[1] + TAIL, 0.0])
                s = nxt[0] - HEAD
        out.append([s, pb, PART_GAP if k < len(parts) - 1 else 0.0])
    return out


SOFT = set("的了著過是把在裡上下給和與跟就都也又從到向對被說出來去得地")   # a line may end after these


def split2(q, names=()):
    """Where to break one phrase into two lines: near the middle, after a particle if one is close, never inside
 a name from the episode glossary (英格桑普 must not become 英／格桑普)."""
    inside = {i for m in names for k in range(len(q)) if q.startswith(m, k) for i in range(k + 1, k + len(m))}
    lo, hi = max(2, round(len(q) * .3)), min(len(q) - 2, round(len(q) * .7))
    cands = [i for i in range(lo, hi + 1) if i not in inside] or [len(q) // 2]
    # …but not between 冒出｜來, 看｜著: a complement or aspect mark belongs to the verb before it
    return min(cands, key=lambda i: abs(i - len(q) / 2) - (3 if q[i - 1] in SOFT else 0) + (4 if q[i] in "來去著了過" else 0))


def chunks(text, t0, t1, n=SUB_CHARS, names=()):
    """v2: a cue as short pieces broken after punctuation, timed by character count. A piece is one line of ≤ n
 characters; a single phrase longer than that stays whole as two balanced lines ("\n"), never cut mid-word
 across two screens."""
    out, cur = [], ""
    for p in re.findall(r"[^，、。？！；：…—]+[，、。？！；：…—」』）]*|[，、。？！；：…—」』）]+", text) or [text]:
        if len(p) > n:
            if cur:
                out.append(cur)
                cur = ""
            k = -(-len(p) // (2 * n))                       # pieces of ≤ 2 lines
            size = -(-len(p) // k)
            for q in (p[i:i + size] for i in range(0, len(p), size)):
                h = split2(q, names) if len(q) > n else len(q)
                out.append(q[:h] + ("\n" + q[h:] if q[h:] else ""))
        elif cur and len(cur) + len(p) > n:
            out.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        out.append(cur)
    out = [x for x in out if x.strip("，、。？！；：…—」』） \n")] or [text]
    total = sum(len(x.replace("\n", "")) for x in out) or 1
    res, t = [], t0
    for x in out:
        d = (t1 - t0) * len(x.replace("\n", "")) / total
        res.append((t, t + d, x.rstrip("，、")))
        t += d
    return res


def timeline(ep, spec):
    """(kept intervals, story seconds, subtitle cues on the short's own clock) for either format."""
    srt = ep / "build" / "zh-Hant.srt"
    if spec.get("v") != 2:
        a, b = spec["start"], spec["end"]
        return [[a, b, 0.0]], b - a, srt_cues(srt, a, b)
    keep, cues, o = plan(ep, spec), [], 0.0
    gl = ep / "script" / "outline.json"
    names = sorted({x for g in (json.loads(gl.read_text()).get("glossary", []) if gl.exists() else [])
                    for x in re.split(r"[·・ ]", g.get("zh", "")) if len(x) > 1}, key=len, reverse=True)
    for ia, ib, gap in keep:
        for t0, t1, text in srt_cues(srt, ia, ib):
            cues += chunks(text, t0 + o, t1 + o, names=names)
        o += ib - ia + gap
    return keep, o, cues


def audio_args(mp4, keep, v2):
    """ffmpeg inputs + filter for the story audio, then the music bed alone under the end card ([o])."""
    bed = ["-ss", "200", "-t", str(CARD_S + 2), "-i", str(ROOT / "music" / "bed-loop.wav")]
    card = f"volume=-2dB,afade=t=in:d=1,afade=t=out:st={CARD_S - 1.2}:d=1.2,atrim=0:{CARD_S}[m]"
    if not v2:                                   # byte-for-byte the pre-10-24 command (published shorts re-render the same)
        a, b, _ = keep[0]
        return ["-ss", str(a), "-t", str(b - a), "-i", str(mp4), *bed, "-filter_complex",
                f"[0:a]afade=t=in:d=0.25,afade=t=out:st={b - a - 1.2:.2f}:d=1.2[s];[1:a]{card};"
                f"[s][m]concat=n=2:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11[o]"]
    ins, fc, labels = [], [], []
    for i, (ia, ib, gap) in enumerate(keep):
        L = ib - ia
        last = i == len(keep) - 1
        out_d = 0.8 if last else 0.05                 # short fades: no click at a cut, no swallowed first word
        if last: out_d = min(out_d, round(L / 2, 3))        # a last segment shorter than 0.8 s gave st<0 → ffmpeg exit 222 (108-b)
        ins += ["-ss", f"{ia:.3f}", "-t", f"{L:.3f}", "-i", str(mp4)]
        fc.append(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,afade=t=in:d=0.04,"
                  f"afade=t=out:st={L - out_d:.3f}:d={out_d}[p{i}]")
        labels.append(f"[p{i}]")
        if gap:
            fc.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{gap}[g{i}]")
            labels.append(f"[g{i}]")
    n = len(keep)
    fc.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1[s]")
    fc.append(f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,{card}")
    # one-pass loudnorm on a 40 s clip overshoots its TP target and AAC adds more (103-a measured −0.3 dBTP);
    # a sample-peak limiter at −3 dBFS after it keeps the encoded file ≤ −1.5 dBTP. v1 above stays byte-for-byte.
    fc.append("[s][m]concat=n=2:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,"
              "alimiter=limit=0.708:attack=1:release=50:level=false[o]")
    return [*ins, *bed, "-filter_complex", ";".join(fc)]


def stroke_text(d, xy, text, font, fill, width, anchor="mm"):
    d.text(xy, text, font=font, fill=fill, stroke_width=width, stroke_fill=(10, 6, 2), anchor=anchor)


def fit(text, path, size, maxw):
    while size > 24:
        f = ImageFont.truetype(path, size)
        if f.getlength(text) <= maxw:
            return f
        size -= 4
    return ImageFont.truetype(path, size)


def wrap(text, font, maxw):
    lines, cur = [], ""
    for ch in text:
        if font.getlength(cur + ch) > maxw and cur:
            lines.append(cur); cur = ""
        cur += ch
    lines = lines + [cur] if cur else lines
    # kinsoku: no line may start with closing punctuation — pull the previous line's last character down with it
    for i in range(1, len(lines)):
        while lines[i] and lines[i][0] in "。，、？！：；」』）…" and len(lines[i - 1]) > 1:
            lines[i - 1], lines[i] = lines[i - 1][:-1], lines[i - 1][-1] + lines[i]
    return lines


def make(n, spec, work):
    ep = next((ROOT / "episodes").glob(f"{n:02d}-*"))
    cfg = json.loads((ep / "episode.json").read_text())
    mp4 = next(ep.glob(f"*-{VAR['suffix']}.mp4"))
    V2 = spec.get("v") == 2
    keep, story, cues = timeline(ep, spec)
    a = keep[0][0]                                 # the art follows the opening line
    dur = story + CARD_S
    # artwork: the episode cover (eye-catching) or the scene illustration playing at that moment
    use_cover = spec.get("art") == "cover" and (ROOT / "covers" / f"{n:02d}.png").exists()   # covers exist for 1–20 so far
    if use_cover:
        art = Image.open(ROOT / "covers" / f"{n:02d}.png").convert("RGB")
    else:
        chap = [l.split(" ", 1) for l in (ep / "build" / "chapters.txt").read_text().strip().splitlines()]
        secs = [sum(int(x) * m for x, m in zip(reversed(c[0].split(":")), (1, 60, 3600))) for c in chap]
        k = max(i for i, s in enumerate(secs[1:-1]) if s <= a + 1.0) if any(s <= a + 1 for s in secs[1:-1]) else 0
        # the original Strand illustration (portrait-ish, greyscale), not the dimmed 16:9 frame of the long video
        from PIL import ImageOps
        src = Image.open(ep / "art" / "paget" / cfg["scenes"][k]["art"]).convert("L")
        art = ImageOps.colorize(ImageOps.autocontrast(src, cutoff=1), black=(30, 18, 8), white=(244, 226, 192))
    if use_cover:
        art = art.resize((1920, 1080), Image.LANCZOS)
        band = art.crop((160, 0, 1760, 1080))       # the subject lives in the right/centre of our covers
    else:
        fitted = art.resize((int(art.width * 1080 / art.height), 1080), Image.LANCZOS)
        band = art.resize((1600, int(art.height * 1600 / art.width)), Image.LANCZOS)
        band = band.crop((0, (band.height - 1080) // 2, 1600, (band.height - 1080) // 2 + 1080)).filter(
            ImageFilter.GaussianBlur(30))
        band = Image.blend(band, Image.new("RGB", band.size, (10, 6, 3)), 0.5)
        band.paste(fitted, ((1600 - fitted.width) // 2, 0))
        art = band.resize((1920, 1080))
    bg = art.resize((int(1920 * H / 1080), H), Image.LANCZOS)
    x0 = (bg.width - W) // 2
    bg = bg.crop((x0, 0, x0 + W, H)).filter(ImageFilter.GaussianBlur(38))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (8, 6, 12)), 0.55)
    bg.save(work / "bg.png"); band.save(work / "art.png")

    # static overlay: brand, night tag, two-line hook
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    stroke_text(d, (W // 2, 170), "枕邊偵探社", ImageFont.truetype(BOLD, 44), (255, 226, 150), 4)
    tag = f"第{show.night(cfg)}夜｜{cfg['title']}"
    tf = ImageFont.truetype(BLACK, 50)
    tw = int(tf.getlength(tag))
    d.rounded_rectangle((W // 2 - tw // 2 - 26, 222, W // 2 + tw // 2 + 26, 300), radius=12, fill=RED)
    d.text((W // 2, 261), tag, font=tf, fill=(255, 255, 255), anchor="mm")
    rows = spec["hook"].split("|")
    hf = min((fit(r, BLACK, 118, W - 120) for r in rows), key=lambda f: f.size)
    for i, r in enumerate(rows):
        stroke_text(d, (W // 2, 400 + i * int(hf.size * 1.12)), r, hf, YELLOW if i == len(rows) - 1 else (255, 255, 255), 10)
    ov.save(work / "static.png")

    # subtitles: one PNG per cue
    subs = []
    sf = ImageFont.truetype(BOLD, 68 if V2 else 62)
    for j, (t0, t1, text) in enumerate(cues):
        img = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
        dd = ImageDraw.Draw(img)
        for li, line in enumerate((text.split("\n") if V2 else wrap(text, sf, W - 120))[:3]):
            stroke_text(dd, (W // 2 - 30, 60 + li * 84), line, sf, CREAM, 7)
        img.save(work / f"sub{j:03d}.png")
        subs.append((t0, t1, work / f"sub{j:03d}.png"))

    # end card
    card = Image.new("RGBA", (W, H), (6, 8, 20, 255))
    d = ImageDraw.Draw(card)
    r = 70
    moon = Image.new("L", (2 * r + 4, 2 * r + 4), 0)
    md = ImageDraw.Draw(moon)
    md.ellipse((2, 2, 2 + 2 * r, 2 + 2 * r), fill=255)
    md.ellipse((2 + int(r * .62), 2 - int(r * .28), 2 + int(r * .62) + 2 * r, 2 - int(r * .28) + 2 * r), fill=0)
    card.paste(Image.new("RGBA", moon.size, (255, 226, 150, 255)), (W // 2 - r, 470), moon)
    rows = (((spec["question"], 70, (255, 255, 255)), (spec["cta"], 72, YELLOW), ("聽到想睡的地方就好", 54, CREAM))
            if V2 else ((spec.get("cta", "今晚 10 點｜完整版廣播劇"), 76, YELLOW), ("聽到想睡的地方就好", 58, CREAM),
                        ("頻道搜尋　枕邊偵探社", 58, (255, 255, 255))))
    for i, (txt, size, col) in enumerate(rows):
        stroke_text(d, (W // 2, 780 + i * 130), txt, fit(txt, BLACK, size, W - 120), col, 6)
    if spec.get("ask") and not V2:
        stroke_text(d, (W // 2, 1250), spec["ask"], fit(spec["ask"], BLACK, 64, W - 120), (255, 255, 255), 6)
    card.save(work / "card.png")

    # audio: the finished mix for [a, b], then the music bed alone under the end card
    aud = work / "a.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *audio_args(mp4, keep, V2), "-map", "[o]", "-ar", "48000", "-ac", "2",
                    str(aud)], check=True)

    # video: blurred backdrop + slow Ken Burns on the illustration + text layers
    frames = int(dur * FPS)
    inputs = ["-loop", "1", "-t", f"{dur:.2f}", "-i", str(work / "bg.png"),
              "-loop", "1", "-t", f"{dur:.2f}", "-i", str(work / "art.png"),
              "-loop", "1", "-t", f"{dur:.2f}", "-i", str(work / "static.png"),
              "-loop", "1", "-t", f"{dur:.2f}", "-i", str(work / "card.png")]
    for _, _, p in subs:
        inputs += ["-loop", "1", "-t", f"{dur:.2f}", "-i", str(p)]
    inputs += ["-i", str(aud)]
    fc = [f"[1:v]zoompan=z='1+0.10*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x730:fps={FPS}[art]",
          f"[0:v][art]overlay=0:{ART_Y}[v0]", "[v0][2:v]overlay=0:0[v1]"]
    last = "v1"
    for j, (t0, t1, _) in enumerate(subs):
        fc.append(f"[{last}][{4 + j}:v]overlay=0:{SUB_Y}:enable='between(t,{t0:.2f},{t1:.2f})'[s{j}]")
        last = f"s{j}"
    fc.append(f"[{last}][3:v]overlay=0:0:enable='gte(t,{story:.2f})',format=yuv420p[vout]")
    out = VAR["shorts_out"] / f"{n:02d}-{spec['id']}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc),
                    "-map", "[vout]", "-map", f"{4 + len(subs)}:a", "-r", str(FPS), "-c:v", "libx264", "-preset",
                    "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-t", f"{dur:.2f}",
                    "-movflags", "+faststart", "-f", "mp4", str(out) + ".part"], check=True)
    Path(str(out) + ".part").replace(out)          # a render cut short never looks finished to --all
    (out.with_suffix(".txt")).write_text(f"【標題】\n{spec['title']}\n\n【說明】\n{spec['desc']}\n", encoding="utf-8")
    # the same cues as a subtitle file for the upload (the video also has them burned in)
    ts = lambda x: "%02d:%02d:%02d,%03d" % (lambda t: (t // 3600000, t // 60000 % 60, t // 1000 % 60, t % 1000))(round(x * 1000))
    srt = "\n".join(f"{i}\n{ts(t0)} --> {ts(t1)}\n{text}\n" for i, (t0, t1, text) in enumerate(cues, 1))
    out.with_suffix(".zh-Hant.srt").write_text(srt, encoding="utf-8")
    if V2:                                         # Bilibili gets Simplified (the same opencc t2s as assemble.py)
        out.with_suffix(".zh-Hans.srt").write_text(subprocess.run(["opencc", "-c", "t2s"], input=srt, capture_output=True,
                                                                  text=True, check=True).stdout, encoding="utf-8")
    return out, dur


KINDS = {"a": "懸念", "b": "反轉", "c": "謎題"}
EXPORT = VAR["shorts_dir"]


def ready(n):
    """A short is cut from the finished long video, so only once that episode's delivery for this variant is current
 (never from a long video that still carries the broken ACE-Step bed)."""
    return variant.current(next((ROOT / "episodes").glob(f"{n:02d}-*")))


def export(n, spec, out):
    """完成Shorts/第NN夜-篇名-a懸念.{mp4,txt,zh-Hant.srt} + one manifest row per short for the uploader."""
    import shutil
    ep = next((ROOT / "episodes").glob(f"{n:02d}-*"))
    cfg = json.loads((ep / "episode.json").read_text())
    stem = f"第{n:02d}夜-{cfg['title']}-{spec['id']}{KINDS.get(spec['id'], '')}"
    EXPORT.mkdir(exist_ok=True)
    for ext in (".mp4", ".txt", ".zh-Hant.srt", ".zh-Hans.srt"):
        if ext == ".zh-Hans.srt" and not out.with_suffix(ext).exists():
            continue                               # v1 shorts never had one
        shutil.copy2(out.with_suffix(ext), EXPORT / f"{stem}{ext}")
    man = EXPORT / "manifest.json"
    rows = json.loads(man.read_text()) if man.exists() else []
    rows = [r for r in rows if r["file"] != f"{stem}.mp4"]
    rows.append({"episode": n, "id": spec["id"], "kind": spec.get("kind", ""), "file": f"{stem}.mp4",
                 "subtitles": f"{stem}.zh-Hant.srt", "title": spec["title"], "description": spec["desc"],
                 "related_long_video": f"第{n:02d}夜-{cfg['title']}.mp4"})
    if (EXPORT / f"{stem}.zh-Hans.srt").exists():
        rows[-1]["subtitles_hans"] = f"{stem}.zh-Hans.srt"     # v2: for Bilibili
    rows.sort(key=lambda r: (r["episode"], r["id"]))
    write_manifest(rows)


LATE = ("完整版今晚 10 點上線", "完整版已在頻道上線")


def write_manifest(rows=None):
    """ every row carries file_version (new bytes → new upload), meta_version (title/description/subtitles →
 edit in place) and description_late (the a short says 「完整版今晚 10 點上線」; once the long video is already
 public that sentence is false, so the uploader uses this one instead)."""
    import os
    import fileversion as fv
    man = EXPORT / "manifest.json"
    if rows is None:
        rows = json.loads(man.read_text()) if man.exists() else []
    for r in rows:
        mp4 = EXPORT / r["file"]
        if not mp4.exists():
            continue
        r["description_late"] = r["description"].replace(*LATE)
        r["file_version"] = fv.file_version(mp4)
        r["meta_version"] = fv.meta_version(r["title"], r["description"], EXPORT / r["subtitles"])
    fv.save()
    tmp = EXPORT / ".manifest.json.tmp"
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, man)


def render(n, only=()):
    specs = json.loads((ROOT / "shorts" / f"{n:02d}.json").read_text())
    for spec in specs:
        if only and spec["id"] not in only:
            continue
        work = ROOT / "shorts" / f"work-{VAR['variant']}" / f"{n:02d}-{spec['id']}"
        work.mkdir(parents=True, exist_ok=True)
        out, dur = make(n, spec, work)
        export(n, spec, out)
        shutil_rmtree(work)
        print(f"{out.name}: {dur:.1f} s", flush=True)


def shutil_rmtree(p):
    import shutil
    shutil.rmtree(p, ignore_errors=True)


def main():
    if sys.argv[1:2] == ["--all"]:
        # every episode with a spec, a music mix, and no short newer than both
        for spec in sorted((ROOT / "shorts").glob("[0-9]*.json"), key=lambda p: int(p.stem)):   # 100+
            n = int(spec.stem)
            if not ready(n):
                continue
            ep = next((ROOT / "episodes").glob(f"{n:02d}-*"))
            mp4 = next(ep.glob(f"*-{VAR['suffix']}.mp4"))
            outs = [VAR["shorts_out"] / f"{n:02d}-{x['id']}.mp4" for x in json.loads(spec.read_text())]
            newest_src = max(spec.stat().st_mtime, mp4.stat().st_mtime)
            newest_src = max(newest_src, (ep / "build" / "zh-Hant.srt").stat().st_mtime)   # cleaned subtitles → redo
            cover = ROOT / "covers" / f"{n:02d}.png"               # a new cover → redo (the a short uses it)
            if cover.exists():
                newest_src = max(newest_src, cover.stat().st_mtime)
            if all(o.exists() and o.stat().st_mtime > newest_src for o in outs):
                continue
            import night_window                    # heavy rendering only 00:15–06:30
            if not night_window.ok(15):
                print("outside the night window — stopping; the next run picks up from here", flush=True)
                break
            render(n)
        write_manifest()
        return
    n = int(sys.argv[1])
    if not ready(n) and "--force" not in sys.argv:
        sys.exit(f"episode {n}: long video has no music mix yet (remix.py) — shorts would carry the old audio")
    render(n, {x for x in sys.argv[2:] if not x.startswith("--")})


if __name__ == "__main__":
    main()
