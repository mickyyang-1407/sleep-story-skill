#!/usr/bin/env python3
"""Find frozen held-chord stretches in a music bed.

Suno sessions sometimes hang on one chord for 1–6 minutes: on a spectrogram a flat band with no note changes. Measure:
per second, the unit-normalised magnitude spectrum 40–2000 Hz (1 Hz bins); its dot product with the spectrum 20 s
earlier; 30 s moving average. Calibrated on 1-Strings: the frozen stretches score 0.92–0.98, real music has a
median ≈0.3 and never passed 0.82 in the five good beds (bass/cello/ambient included).

Usage: bed_check.py FILE [FILE …] → prints flagged runs (score > 0.85 for ≥ 20 s); exit 1 if any
"""
import subprocess, sys
import numpy as np

SR, LAG, AVG, TH, MIN_S = 8000, 20, 30, 0.85, 20


def score(path):
    x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                                     capture_output=True, check=True).stdout, np.float32)
    n, win, S = len(x) // SR, np.hanning(SR), []
    for i in range(n):
        m = np.abs(np.fft.rfft(x[i * SR:(i + 1) * SR] * win))[40:2000]
        S.append(m / (np.linalg.norm(m) + 1e-9))
    S = np.array(S)
    s = np.zeros(n)
    s[LAG:] = (S[LAG:] * S[:-LAG]).sum(1)
    return np.convolve(s, np.ones(AVG) / AVG, "same")


def runs(s):
    out, i = [], 0
    while i < len(s):
        if s[i] > TH:
            j = i
            while j < len(s) and s[j] > TH:
                j += 1
            if j - i >= MIN_S:
                out.append((max(0, i - LAG), j, float(s[i:j].max())))
            i = j
        else:
            i += 1
    return out


def main():
    bad = 0
    for p in sys.argv[1:]:
        s, r = score(p), None
        r = runs(s)
        bad += bool(r)
        mm = lambda t: f"{t // 60}:{t % 60:02d}"
        print(f"{'FROZEN' if r else 'ok':6s} {p}  max {s.max():.2f}", *[f"\n   {mm(a)}–{mm(b)} ({b - a}s, {m:.2f})" for a, b, m in r])
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
