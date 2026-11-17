#!/usr/bin/env python3
"""Assemble narration (loudness-normalised), subtitles, chapters and video for one episode.

Usage: assemble.py <episode_dir> [--tail-seconds 10] [--reuse-video] [--nomusic]

Two deliveries per episode :
 default music bed from music/pool/*.flac, rotated by episode number → NN-…-preview.mp4, build/assemble-report.json
 --nomusic narration only → NN-…-nomusic.mp4, build/assemble-report-nomusic.json
"""
import json, os, re, subprocess, sys, wave
from pathlib import Path

import numpy as np

SR_IN, SR = 44100, 48000
TARGET_I, TARGET_LRA, MASTER_TP, DELIVERY_TP = -14.0, 11.0, -1.5, -1.0
XFADE, FPS, CUE_MAX = 2.0, 24, 22
ROOT = Path(__file__).resolve().parent.parent
# the maintainer on the Suno bed: → −15 → −18 LU, and the ducker under speech 2:1 → 4:1
# v3: halfway between v1 (−15 LU, 2:1) and v2 (−18 LU, 4:1)
MUSIC_REL, BED_LUFS, DUCK_RATIO = -16.5, -23.0, 3
POOL = ROOT / "music" / "pool"
ROTATION = ["1-Strings-edit2.flac", "2-Steady-Cello.flac", "3-Standing-Crew-sacred-chamber.flac", "4-double-bass.flac",
            "5-Organic-ambient.flac", "6-string-quartet.flac"]      # episode n → slot (n − 1) % 6 # Suno sessions , one per episode in turn, each −23 LUFS


# the Suno prompt each new bed came from (suno_master.py 曲目對照.txt) → the seasons it suits
NEUTRAL_BEDS = ("C04", "C10", "C11", "C14", "C15", "C20")
ENGLAND = ("C01", "C02", "C03", "C12", "C16")
SEASON_BEDS = {"": ENGLAND, "亂步": ("C05", "C17"), "阿嘉莎": ("C07", "C13") + ENGLAND, "布朗神父": ("C09",) + ENGLAND,
               "羅蘋": ("C08", "C19"), "霍桑": ("C06", "C18")}


def bed_for(number, playlist=False):
    """The bed an episode uses: SD_MUSIC_BED (a test candidate) > music/pool rotation > the old single loop."""
    if os.environ.get("SD_MUSIC_BED"):
        return Path(os.environ["SD_MUSIC_BED"])
    # the six-slot rotation stays fixed (so every episode keeps its bed); a slot whose bed is missing hands
    # its episodes round the remaining beds. Slot 1 = 1-Strings-edit:
    # — the two sustained stretches of the Suno source (9:36–13:44 and 67:01–end) cut out, 62.8 min
    # edit still held four more held-chord stretches (same spectral fingerprint,
    # 10 s-lag similarity ≈0.9 for 2–4 min; the other five beds never exceed 0.85) → 1-Strings-edit2: cut 5:25–11:48,
    # 16:43–19:48, 31:25–35:23 and 58:39–end (edit timeline), 4 s equal-power crossfades, 45.0 min, −23 LUFS
    # 80 new Suno beds (music/pool/suno2-NNN-Cxx.flac, mastered by
    # suno_master.py). Episodes produced before keep their bed (music/bed-legacy.json) so nothing needs a remix;
    # every later episode rotates through its season's beds — the ones written for that setting plus the neutral ones
    legacy = ROOT / "music" / "bed-legacy.json"
    kept = json.loads(legacy.read_text())["beds"] if legacy.exists() else {}
    old = kept.get(str(number))
    if old and (POOL / old).exists():
        return POOL / old
    new = sorted(POOL.glob("suno2-*.flac")) if POOL.exists() else []
    if new:
        import season
        s = season.of_number(number)
        want = SEASON_BEDS.get(s["label"], ()) + NEUTRAL_BEDS
        mine = [p for p in new if p.stem.split("-")[-1] in want] or new
        # round-robin over the prompts (neighbouring episodes get different instruments), counted from the season's
        # first episode that is not a legacy one
        by = {}
        for p in mine:
            by.setdefault(p.stem.split("-")[-1], []).append(p)
        order = [q for i in range(max(map(len, by.values()))) for c in want if c in by and i < len(by[c]) for q in [by[c][i]]]
        k = sum(1 for m in range(s["first"], number) if str(m) not in kept)
        return order[k % len(order):] + order[:k % len(order)] if playlist else order[k % len(order)]
    live = sorted(POOL.glob("*.flac")) if POOL.exists() else []
    if not live:
        return ROOT / "music" / "bed-loop.wav"
    slot = ROTATION[(number - 1) % len(ROTATION)]
    hit = [p for p in live if p.name == slot]
    return hit[0] if hit else live[((number - 1) // len(ROTATION)) % len(live)]


def bed_chain(number, total, out):
    """ the new Suno beds are 4–6 min each — chain the season's beds from this episode's one on with 12 s
 12 s overlaps (each bed carries its own 4 s fade-in and 8 s fade-out, so the overlap just sums them) until the episode is covered (instead of looping one piece ten times). Returns (wav, names)."""
    chain, have = [], 0.0
    for q in bed_for(number, playlist=True) * 4:
        chain.append(q)
        have += float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(q)]).stdout) - 12
        if have >= total + 10:
            break
    chained = out / "bed-chain.wav"
    ins = sum((["-i", str(q)] for q in chain), [])
    lab, parts = "[0:a]", []
    for i in range(1, len(chain)):
        parts.append(f"{lab}[{i}:a]acrossfade=d=12:c1=nofade:c2=nofade[x{i}]")
        lab = f"[x{i}]"
    sh(["nice", "-n", "10", "ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(parts) or "[0:a]anull[x0]",
        "-map", lab if parts else "[x0]", "-c:a", "pcm_f32le", str(chained)])
    return chained, [q.name for q in chain]


def music_settings():
    return {"rel_lu": MUSIC_REL, "duck_ratio": DUCK_RATIO}     # preview: −20 left the bed 31–33 dB under speech in the pauses # bed level: LU under the narration; music.py normalises the bed to −23


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def loudness(path, full=False):
    err = subprocess.run(["nice", "-n", "10", "ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
                          "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    summary = err[err.rfind("Summary:"):]
    i = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summary).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary).group(1))
    if not full:
        return i, tp
    thresh = float(re.search(r"Integrated loudness:.*?Threshold:\s+(-?[\d.]+) LUFS", summary, re.S).group(1))
    lra = float(re.search(r"LRA:\s+(-?[\d.]+) LU", summary).group(1))
    return {"input_i": i, "input_tp": tp, "input_lra": lra, "input_thresh": thresh, "target_offset": 0.0}


def last_json(stderr):
    # loudnorm prints its JSON block, then ffmpeg prints summary lines after it
    return json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr)[-1])


def read_wav(path):
    with wave.open(str(path)) as w:
        assert w.getframerate() == SR_IN and w.getnchannels() == 1 and w.getsampwidth() == 2, path
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def ts(sec, srt=True):
    if srt:   # round to whole ms first — 2339.9996 s used to print "00:38:60,000" (YouTube rejects it)
        h, rem = divmod(round(sec * 1000), 3600000); m, rem = divmod(rem, 60000); s, ms = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    h, rem = divmod(sec, 3600); m, s = divmod(rem, 60)
    # YouTube chapters: the first stamp must read 0:00; hours only when needed
    return f"{int(h)}:{int(m):02d}:{int(s):02d}" if h else f"{int(m)}:{int(s):02d}"


def split_cue(text, t0, t1):
    parts = [p for p in re.split(r"(?<=[，、；：。？])", text) if p]
    chunks, cur = [], ""
    for p in parts:
        if cur and len(cur) + len(p) > CUE_MAX:
            chunks.append(cur); cur = p
        else:
            cur += p
    if cur:
        chunks.append(cur)
    total = sum(len(c) for c in chunks)
    out, t = [], t0
    for c in chunks:
        dt = (t1 - t0) * len(c) / total
        out.append((t, t + dt, c.rstrip("，、；：")))
        t += dt
    return out


def timing(ep, tail, load=True):
    """Segment clock of the narration (shared with revideo.py, which only needs the times — load=False reads
 the wav headers instead of the samples)."""
    seg_dir = ep / "audio" / "seg"
    timeline = json.loads((ep / "audio" / "timeline.json").read_text())
    pieces, starts, t = [], {}, 0.0
    for seg in timeline:
        if load:
            pieces.append(np.zeros(int(seg["gap_before"] * SR_IN), np.int16))
        t += seg["gap_before"]
        if load:
            a = read_wav(seg_dir / f"{seg['id']}.wav"); dur = len(a) / SR_IN
        else:
            with wave.open(str(seg_dir / f"{seg['id']}.wav")) as w:
                dur = w.getnframes() / w.getframerate()
        starts[seg["id"]] = (t, t + dur)
        if load:
            pieces.append(a)
        t += dur
    scene_start = {}
    for seg in timeline:
        if seg.get("scene") is not None:
            scene_start.setdefault(seg["scene"], starts[seg["id"]][0])
    story_end = t
    if load:
        pieces.append(np.zeros(int(tail * SR_IN), np.int16))
    return timeline, starts, scene_start, story_end, t + tail, pieces


def para_clock(ep, timeline, starts):
    """Start time of every script paragraph: a drama segment holds several paragraphs, so the segment's time is
 shared out by the length of each paragraph's Chinese text (, for art_cues)."""
    zh = {r["id"]: len(r["zh"]) for r in json.loads((ep / "script" / "script.json").read_text())}
    out = {}
    for seg in timeline:
        paras = seg.get("paras", [])
        t0, t1 = starts[seg["id"]]
        total = sum(zh.get(p, 0) for p in paras) or 1
        done = 0
        for p in paras:
            out[p] = t0 + (t1 - t0) * done / total
            done += zh.get(p, 0)
    return out


def clips_for(ep, cfg, timeline, starts, scene_start):
    """Pictures on screen and when each one comes in. Default: one per scene. episode.json "art_cues" [{"para": "P045", "art": "plates/p03-x.png"}, …] changes the picture at
 the paragraph it shows instead (frames/cue-<stem>.png, written by art.py)."""
    frames = ep / "art" / "frames"
    if not cfg.get("art_cues"):
        return [(frames / f"scene-{s['art'].split('-')[0]}.png", scene_start[k] - 1.0) for k, s in enumerate(cfg["scenes"])]
    para_t = para_clock(ep, timeline, starts)
    first = scene_start[0] - 1.0
    out = []
    for c in cfg["art_cues"]:
        t = max(first, para_t[c["para"]] - 1.0) if out else first      # the first picture opens the story
        if out and t < out[-1][1] + 2 * XFADE:
            raise SystemExit(f"art_cues: {c['para']} comes {t - out[-1][1]:.1f}s after the previous picture")
        out.append((frames / f"cue-{Path(c['art']).stem}.png", t))
    return out


def make_video(ep, cfg, timeline, starts, scene_start, total, video):
    """Title → pictures → end card → black, cross-faded (a function so revideo.py can redraw the picture track)."""
    frames = ep / "art" / "frames"
    clips = [(frames / "title.png", 0.0)] + clips_for(ep, cfg, timeline, starts, scene_start)
    clips.append((frames / "end.png", starts["OUTRO"][0] - 1.0))
    black_at = starts["OUTRO"][1] + 8.0
    T = [c[1] for c in clips] + [black_at]
    durs = [T[1]] + [T[k + 1] - T[k] + XFADE for k in range(1, len(T) - 1)] + [total - black_at + XFADE]
    inputs, fc = [], []
    for (img, _), d in zip(clips, durs):
        inputs += ["-framerate", str(FPS), "-loop", "1", "-t", f"{d:.3f}", "-i", str(img)]
    inputs += ["-f", "lavfi", "-t", f"{durs[-1]:.3f}", "-i", f"color=c=black:s=1920x1080:r={FPS}"]
    n = len(clips) + 1
    prev = "[0:v]format=yuv420p,setsar=1[v0]"
    fc.append(prev)
    for k in range(1, n):
        fc.append(f"[{k}:v]format=yuv420p,setsar=1[s{k}]")
        fc.append(f"[v{k - 1}][s{k}]xfade=transition=fade:duration={XFADE}:offset={T[k] - XFADE:.3f}[v{k}]")
    sh(["nice", "-n", "10", "ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc),
        "-map", f"[v{n - 1}]", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage",
        "-crf", "20", "-pix_fmt", "yuv420p", "-t", f"{total:.3f}", str(video)])
    return clips


def main():
    ep = Path(sys.argv[1]).expanduser()
    tail = float(sys.argv[sys.argv.index("--tail-seconds") + 1]) if "--tail-seconds" in sys.argv else 10.0
    cfg = json.loads((ep / "episode.json").read_text())
    seg_dir, out = ep / "audio" / "seg", ep / "build"
    out.mkdir(exist_ok=True)
    # 1) narration timeline, written by tts.py: segment order, the silence before each one, scene membership
    timeline, starts, scene_start, story_end, total, pieces = timing(ep, tail)
    narr44 = out / "narration-44k.wav"
    with wave.open(str(narr44), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR_IN)
        w.writeframes(np.concatenate(pieces).tobytes())

    # 2) loudness to the YouTube playback reference
    # two-pass EBU R128 loudnorm; master TP −1.5 leaves room for AAC overshoot, delivered AAC must be ≤ −1.0 dBTP
    narr48 = out / "narration-48k.wav"
    # this ffmpeg lists soxr but is built without libsoxr → high-quality swr instead
    sh(["ffmpeg", "-y", "-v", "error", "-i", str(narr44), "-af",
        "aresample=48000:resampler=swr:filter_size=256:phase_shift=10:cutoff=0.97:dither_method=triangular,"
        "pan=stereo|c0=c0|c1=c0", "-c:a", "pcm_s24le", str(narr48)])
    # 1b) music bed: music/bed-loop.wav looped under the whole episode,
    # MUSIC_REL LU under the narration, ducked a few dB more while someone is speaking (sidechain), faded in over
    # the intro and out with the story; episode.json "music": false turns it off
    # tuning on a 90 s ep-2 excerpt: threshold 0.02/ratio 3 buried the bed 31 LU under the voice;
    # 0.06/ratio 2 on the raw narration ≈ −20 LU in the pauses, ≈ −23 LU under speech
    nomusic = "--nomusic" in sys.argv
    bed = bed_for(cfg["number"])
    music = {"on": not nomusic and bool(cfg.get("music", True)) and bed.exists()}
    if music["on"] and bed.name.startswith("suno2-"):
        bed_src, music["chain"] = bed_chain(cfg["number"], total, out)
    else:
        bed_src = bed
    if music["on"]:
        n_only = loudness(narr48)[0]
        gain = n_only + MUSIC_REL - BED_LUFS
        mixed = out / "mix-48k.wav"
        fc = (f"[1:a]atrim=0:{total:.3f},asetpts=N/SR/TB,volume={gain:.2f}dB,afade=t=in:d=6,"
              f"afade=t=out:st={max(0.0, story_end - 4):.3f}:d=10[m];"
              f"[0:a]asplit=2[n][key];"
              f"[m][key]sidechaincompress=threshold=0.06:ratio={DUCK_RATIO}:attack=200:release=1800:knee=6[md];"
              f"[n][md]amix=inputs=2:normalize=0:duration=first[out]")
        sh(["nice", "-n", "10", "ffmpeg", "-y", "-v", "error", "-i", str(narr48), "-stream_loop", "-1", "-i", str(bed_src),
            "-filter_complex", fc, "-map", "[out]", "-t", f"{total:.3f}", "-c:a", "pcm_s24le", str(mixed)])
        narr48.unlink()
        mixed.rename(narr48)
        if bed_src != bed:
            bed_src.unlink(missing_ok=True)
        music.update(**music_settings(), bed=bed.name, narration_lufs=n_only, gain_db=round(gain, 2))
    # pass 1 = EBU R128 measurement (ebur128 is ~20× faster than a loudnorm analysis pass; same four numbers)
    p1 = loudness(narr48, full=True)
    n_i, n_tp = p1["input_i"], p1["input_tp"]
    master = out / ("master-48k24-nomusic.wav" if nomusic else "master-48k24.wav")
    # narration peaks sit ~19 dB over its loudness, so loudnorm runs dynamic (true-peak limiting) and
    # lands 0.4–0.7 LU under target (episodes 6–34 at −14.6, outside ±0.5) — aim the pass by the miss and redo
    def master_pass(mtp):
        aim = TARGET_I
        for _ in range(3):
            ln = f"loudnorm=I={aim:.1f}:TP={mtp}:LRA={TARGET_LRA}"
            p2_err = sh(["nice", "-n", "10", "ffmpeg", "-y", "-hide_banner", "-nostats", "-i", str(narr48), "-af",
                         f"{ln}:measured_I={p1['input_i']}:measured_TP={p1['input_tp']}:measured_LRA={p1['input_lra']}:"
                         f"measured_thresh={p1['input_thresh']}:offset={p1['target_offset']}:linear=true:print_format=json",
                         "-ar", "48000", "-c:a", "pcm_s24le", str(master)]).stderr
            p2 = last_json(p2_err)
            m_i, m_tp = loudness(master)
            if abs(m_i - TARGET_I) <= 0.2 or aim >= TARGET_I + 2.0:
                break
            aim = min(aim + TARGET_I - m_i, TARGET_I + 2.0)
        # episodes 16/46: quiet narration (−20 LUFS) with hot peaks — loudnorm tops out at aim −12 and still
        # lands −14.7/−14.9; make up the rest with plain gain into a peak limiter set under the master TP
        if m_i < TARGET_I - 0.2:
            boosted = out / "master-boost.wav"
            lim = 10 ** ((mtp - 0.7) / 20)
            sh(["nice", "-n", "10", "ffmpeg", "-y", "-v", "error", "-i", str(master), "-af",
                f"volume={TARGET_I - m_i:.2f}dB,alimiter=limit={lim:.4f}:attack=5:release=100:level=false",
                "-ar", "48000", "-c:a", "pcm_s24le", str(boosted)])
            boosted.replace(master)
            m_i, m_tp = loudness(master)
        return p2, aim, m_i, m_tp
    mtp = MASTER_TP
    p2, aim, m_i, m_tp = master_pass(mtp)

    # 5) subtitles
    cues = []
    for sid in [seg["id"] for seg in timeline]:
        base = starts[sid][0]
        for s in json.loads((seg_dir / f"{sid}.sub.json").read_text()):
            cues += split_cue(s["text"].strip(), base + s["time_begin"] / 1000, base + s["time_end"] / 1000)
    from srtfix import clean                     # no punctuation-only or zero-length cues (YouTube rejects them)
    cues = clean(cues)
    srt = "\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{c}\n" for i, (a, b, c) in enumerate(cues, 1))
    (out / "zh-Hant.srt").write_text(srt, encoding="utf-8")
    hans = subprocess.run(["opencc", "-c", "t2s"], input=srt, capture_output=True, text=True, check=True).stdout
    (out / "zh-Hans.srt").write_text(hans, encoding="utf-8")

    # 6) chapters
    chapters = [(0.0, "開場")] + [(scene_start[k] - 1.0, s["chapter"]) for k, s in enumerate(cfg["scenes"])]
    chapters.append((starts["OUTRO"][0] - 1.0, "晚安"))
    (out / "chapters.txt").write_text("\n".join(f"{ts(t0, srt=False)} {name}" for t0, name in chapters) + "\n",
                                      encoding="utf-8")

    # 7) video: title → scenes → end card → black, cross-fades
    video = out / "video.mp4"
    if not ("--reuse-video" in sys.argv and video.exists()):
        make_video(ep, cfg, timeline, starts, scene_start, total, video)

    # 8) final mux: video + AAC + soft subtitles
    final = ep / f"{cfg['number']:02d}-{cfg['title_en'].lower().replace(' ', '-')}-{'nomusic' if nomusic else 'preview'}.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(master), "-i", str(out / "zh-Hant.srt"),
        "-map", "0:v", "-map", "1:a", "-map", "2:s", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
        "-c:s", "mov_text", "-metadata:s:s:0", "language=zho", "-metadata:s:s:0", "title=繁體中文",
        "-movflags", "+faststart", "-t", f"{total:.3f}", str(final)])  # not -shortest: the subtitle track ends with the story

    a_i, a_tp = loudness(final)
    # episode 29: the AAC encode overshot the −1.4 dBTP master by 0.8 dB (−0.6, out of spec) —
    # when the delivery misses −1.0, master again with 0.5 dB more headroom and re-mux the audio only
    while a_tp > DELIVERY_TP and mtp > MASTER_TP - 1.5:
        mtp = round(mtp - 0.5, 1)
        p2, aim, m_i, m_tp = master_pass(mtp)
        sh(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(master), "-i", str(out / "zh-Hant.srt"),
            "-map", "0:v", "-map", "1:a", "-map", "2:s", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
            "-c:s", "mov_text", "-metadata:s:s:0", "language=zho", "-metadata:s:s:0", "title=繁體中文",
            "-movflags", "+faststart", "-t", f"{total:.3f}", str(final)])
        a_i, a_tp = loudness(final)
    report = {"total_s": round(total, 2), "story_end_s": round(story_end, 2), "tail_s": tail,
              "narration_raw": {"I": n_i, "TP": n_tp}, "loudnorm": {"type": p2.get("normalization_type"),
              "target": {"I": TARGET_I, "TP": mtp, "LRA": TARGET_LRA}, "aim_I": round(aim, 1)}, "master": {"I": m_i, "TP": m_tp},
              "music": music, "aac": {"I": a_i, "TP": a_tp, "ok": a_tp <= DELIVERY_TP and abs(a_i - TARGET_I) <= 0.5}, "cues": len(cues),
              "chapters": [(ts(a, srt=False), b) for a, b in chapters], "final": str(final)}
    if nomusic:
        master.unlink(missing_ok=True)          # the mp4 carries it; keep only the music master on disk
    (out / ("assemble-report-nomusic.json" if nomusic else "assemble-report.json")).write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
