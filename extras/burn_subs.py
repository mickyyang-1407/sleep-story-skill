"""Burn the episode's own zh-Hant.srt into the picture so phones show it without turning on captions.
Reuses shorts.py's PIL text helpers (stroke_text / wrap) and its overlay=enable method; audio is copied untouched.
Usage: python3 extras/burn_subs.py <in.mp4> <in.srt> <out.mp4> (heavy: one libx264 pass — run in the night window)"""
import re, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

M = Path(__file__).resolve().parent
sys.path.insert(0, str(M.parent / "tools"))       # extras/ sits next to tools/ in the package
import shorts  # noqa: E402

W, H, SIZE, MAXW, Y = 1920, 1080, 54, 1500, 1000


def cue_image(text):
    """One subtitle cue as a transparent 1920×1080 layer (bottom-centred, up to two lines, baseline y 1000)."""
    font = ImageFont.truetype(shorts.BOLD, SIZE)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for k, line in enumerate(reversed(shorts.wrap(text, font, MAXW))):
        shorts.stroke_text(d, (W // 2, Y - k * int(SIZE * 1.35)), line, font, (246, 238, 222), 5, anchor="ms")
    return img


def main():
    src, srt, dst = map(Path, sys.argv[1:4])
    cues = []
    for blk in srt.read_text(encoding="utf-8").strip().split("\n\n"):
        L = blk.split("\n")
        if len(L) < 3:
            continue
        a, b = [sum(float(x) * m for x, m in zip(re.split("[:,]", s)[:3], (3600, 60, 1))) + int(re.split("[:,]", s)[3]) / 1000
                for s in L[1].split(" --> ")]
        cues.append((a, b, "".join(L[2:])))
    work = Path(tempfile.mkdtemp(prefix="burnsubs-"))
    ins, fc, last = [], [], "0:v"
    for j, (a, b, t) in enumerate(cues):
        p = work / f"s{j:03d}.png"; cue_image(t).save(p)
        ins += ["-i", str(p)]
        fc.append(f"[{last}][{j + 1}:v]overlay=0:0:enable='between(t,{a:.3f},{b:.3f})'[v{j}]")
        last = f"v{j}"
    cmd = ["nice", "-n", "10", "ffmpeg", "-y", "-v", "error", "-i", str(src), *ins, "-filter_complex", ";".join(fc),
           "-map", f"[{last}]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(dst)]
    subprocess.run(cmd, check=True)
    for p in work.iterdir():
        p.unlink()
    work.rmdir()
    print(f"burned {len(cues)} cues → {dst}")


if __name__ == "__main__":
    main()
