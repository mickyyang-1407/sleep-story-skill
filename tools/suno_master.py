#!/usr/bin/env python3
"""Cut, check and master the Pro Tools recordings of the Suno bed sessions .

Usage: suno_master.py [SRC_DIR] [OUT_DIR] (defaults music/suno → music/suno-mastered; the recordings are never touched)

Per recording (48 kHz/24-bit stereo, several Suno songs back to back, played from the browser):
 1. cut points: quiet runs (RMS < QUIET dBFS for ≥ 0.75 s); a piece still longer than MAX_PIECE is cut at the quietest
 second near every 360 s (gapless song changes); pieces shorter than MIN_PIECE are dropped (stray tails and gaps)
 2. edges: leading/trailing quiet trimmed
 3. frozen held chords: bed_check.score; flagged runs are cut out and the rest kept as separate pieces
 4. master: 35 Hz high-pass, gentle 2:1 compression, two-pass loudnorm to BED_LUFS / TP −3 dBTP, 4 s fade-in,
 8 s fade-out, 48 kHz 24-bit
Writes OUT_DIR/<recording>-NN.wav and OUT_DIR/report.json (clipping in the source, every cut and why, final loudness).
"""
import json, re, subprocess, sys
from pathlib import Path

import numpy as np

import bed_check

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "music" / "suno"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "music" / "suno-mastered"
AR = 8000                       # analysis rate
QUIET, QUIET_MIN = -48.0, 0.75  # dBFS RMS, seconds
EDGE = -45.0
MIN_PIECE, MAX_PIECE, SONG = 120.0, 400.0, 360.0
JOIN_GAP = 2.5
BED_LUFS, TP, LRA = -23.0, -3.0, 7.0
FADE_IN, FADE_OUT = 4.0, 8.0


def decode(path, rate, ch):
    return np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", str(ch), "-ar", str(rate),
                                         "-f", "f32le", "-"], capture_output=True, check=True).stdout, np.float32)


def rms_db(x, hop):
    n = len(x) // hop
    r = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1))
    return 20 * np.log10(r + 1e-9)


def cut_points(env, step):
    """Centres of quiet runs, in seconds."""
    q, cuts, i = env < QUIET, [], 0
    while i < len(q):
        if q[i]:
            j = i
            while j < len(q) and q[j]:
                j += 1
            if (j - i) * step >= QUIET_MIN:
                cuts.append(((i + j) / 2) * step)
            i = j
        else:
            i += 1
    return cuts


def split_long(a, b, env1):
    """Gapless song changes: cut a long piece at the quietest second within ±8 s of every SONG mark."""
    out, t = [], a
    while b - t > MAX_PIECE:
        lo, hi = int(t + SONG - 8), int(min(t + SONG + 8, b - MIN_PIECE))
        if hi <= lo:
            break
        c = lo + int(np.argmin(env1[lo:hi]))
        out.append((t, float(c), "gapless song change"))
        t = float(c)
    out.append((t, b, ""))
    return out


def master(src, a, b, dst):
    seg = dst.with_suffix(".raw.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(src),
                    "-af", "highpass=f=35,acompressor=threshold=-24dB:ratio=2:attack=50:release=600:knee=6",
                    "-c:a", "pcm_f32le", str(seg)], check=True)
    m = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(seg), "-af",
                        f"loudnorm=I={BED_LUFS}:TP={TP}:LRA={LRA}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    p = json.loads(re.findall(r"\{[^{}]*\}", m, re.S)[-1])
    dur = b - a
    af = (f"loudnorm=I={BED_LUFS}:TP={TP}:LRA={LRA}:measured_I={p['input_i']}:measured_TP={p['input_tp']}:"
          f"measured_LRA={p['input_lra']}:measured_thresh={p['input_thresh']}:offset={p['target_offset']}:linear=true,"
          f"aresample=48000,afade=t=in:d={FADE_IN},afade=t=out:st={dur - FADE_OUT:.3f}:d={FADE_OUT}")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(seg), "-af", af, "-ar", "48000", "-c:a", "pcm_s24le",
                    str(dst)], check=True)
    seg.unlink()
    e = subprocess.run(["ffmpeg", "-nostats", "-i", str(dst), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])
    tpk = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])
    lra = float(re.findall(r"LRA:\s+(-?[\d.]+) LU", e)[-1])
    return {"lufs": I, "true_peak": tpk, "lra": lra}


def main():
    OUT.mkdir(exist_ok=True)
    report, k = {}, 0
    for src in sorted(SRC.glob("*.wav")):
        name = re.sub(r"[^A-Za-z0-9]+", "-", src.stem).strip("-")
        st = decode(src, 48000, 2)
        clip = int((np.abs(st) >= 0.9999).sum())
        peak = float(20 * np.log10(np.abs(st).max() + 1e-12))
        del st
        x = decode(src, AR, 1)
        step = 0.25
        env = rms_db(x, int(AR * step))
        env1 = rms_db(x, AR)
        total = len(x) / AR
        cuts = [0.0] + cut_points(env, step) + [total]
        pieces, dropped, raw, merged = [], [], [], []
        for a, b in zip(cuts, cuts[1:]):
            for pa, pb, why in split_long(a, b, env1):
                # trim quiet edges
                i0, i1 = int(pa / step), int(pb / step)
                loud = np.where(env[i0:i1] > EDGE)[0]
                if not len(loud):
                    continue
                ta, tb = (i0 + loud[0]) * step, (i0 + loud[-1] + 1) * step
                raw.append((ta, tb, why))
        # a short pause inside one song (Suno songs often breathe for ~1 s around 5:00) is not a song change:
        # rejoin when the gap is short and the two parts together still fit in one song
        for ta, tb, why in raw:
            if merged and ta - merged[-1][1] <= JOIN_GAP and tb - merged[-1][0] <= SONG + 4 and not why:
                merged[-1] = (merged[-1][0], tb, merged[-1][2])
            else:
                merged.append((ta, tb, why))
        for ta, tb, why in merged:
            (pieces if tb - ta >= MIN_PIECE else dropped).append((ta, tb, why))
        rec = {"source": src.name, "duration_s": round(total, 1), "source_peak_dbfs": round(peak, 2),
               "source_clipped_samples": clip, "pieces": [], "dropped_short": [(round(a, 1), round(b, 1)) for a, b, _ in dropped]}
        for a, b, why in pieces:
            # frozen held chords inside the piece
            tmp = OUT / f".{name}-check.wav"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(src),
                            "-ac", "1", "-ar", str(AR), str(tmp)], check=True)
            frozen = bed_check.runs(bed_check.score(str(tmp)))
            tmp.unlink()
            keep, t = [], a
            for fa, fb, sc in frozen:
                if a + fa - t >= MIN_PIECE:
                    keep.append((t, a + fa))
                t = max(t, a + fb)
            if b - t >= MIN_PIECE:
                keep.append((t, b))
            for ka, kb in keep:
                k += 1
                dst = OUT / f"bed-{k:03d}.wav"
                info = master(src, ka, kb, dst)
                rec["pieces"].append({"file": dst.name, "from_s": round(ka, 1), "to_s": round(kb, 1),
                                      "length_s": round(kb - ka, 1), "cut_reason": why, **info})
                print(f"{dst.name}: {ka:7.1f}–{kb:7.1f}s ({(kb - ka) / 60:.1f} min) {info}", flush=True)
            if frozen:
                rec.setdefault("frozen_cut", []).append({"piece": [round(a, 1), round(b, 1)],
                                                        "runs_s": [(round(a + fa, 1), round(a + fb, 1), round(sc, 3)) for fa, fb, sc in frozen]})
        report[src.name] = rec
        (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
        print(f"== {src.name}: {len(rec['pieces'])} pieces, peak {peak:.2f} dBFS, clipped {clip}, "
              f"frozen {sum(len(f['runs_s']) for f in rec.get('frozen_cut', []))}", flush=True)


if __name__ == "__main__":
    main()
