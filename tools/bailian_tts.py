"""Bailian Token Plan TTS (qwen-audio-3.0-tts-plus); e.g. narrator longanlingxin + a bedtime instruction. drama_tts.synth hands every voice id
"bailian:<voice>" here; the call's emotion slot carries the instruction. MiniMax pause tags <#s#> are not understood by
Bailian, so each sentence is its own request and the pause is real silence — which also gives exact sentence times for
the .sub.json. Output: one 44.1 kHz mono 16-bit wav, like T2A's."""
import json, os, re, subprocess, tempfile, time, urllib.error, urllib.request, wave
from pathlib import Path

import numpy as np

URL = os.environ.get("BAILIAN_TTS_URL", "https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer")
MODEL = "qwen-audio-3.0-tts-plus"
KEY = os.environ.get("BAILIAN_API_KEY", "").strip()      # [share export] reader's own key


def _one(text, voice, instruction):
    inp = {"text": text, "voice": voice, "format": "wav", "sample_rate": 24000, **({"instruction": instruction} if instruction else {})}
    body = json.dumps({"model": MODEL, "input": inp}).encode()
    for attempt in range(8):
        try:
            req = urllib.request.Request(URL, data=body, method="POST",
                                         headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
            d = json.load(urllib.request.urlopen(req, timeout=180))
            raw = urllib.request.urlopen(d["output"]["audio"]["url"], timeout=180).read()
            break
        except urllib.error.HTTPError as e:
            msg = e.read()[:300]
            # a spent month quota (Throttling.AllocationQuota) was retried 8× per sentence like a rate limit —
            # 550 sat ~6 h holding .tts.lock and both produce lanes lost the night waiting behind it
            if e.code == 429 and b"AllocationQuota" in msg:
                raise RuntimeError(f"bailian quota exhausted: {msg}")
            if e.code in (429, 500, 502, 503) and attempt < 7:
                time.sleep(15 * (attempt + 1)); continue
            raise RuntimeError(f"bailian {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError, KeyError) as e:
            if attempt < 7:
                time.sleep(15); continue
            raise
    with tempfile.TemporaryDirectory() as td:
        src, dst = Path(td) / "a.wav", Path(td) / "b.wav"
        src.write_bytes(raw)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", "aresample=44100:filter_size=64:phase_shift=10:cutoff=0.97",
                        "-ac", "1", "-c:a", "pcm_s16le", str(dst)], check=True)
        with wave.open(str(dst)) as w:
            return np.frombuffer(w.readframes(w.getnframes()), np.int16)


def synth(text, voice, instruction, wav_path, sub_path, sr=44100):
    """Returns the characters sent. Sentences split at <#s#>; s seconds of silence between them."""
    parts = re.split(r"<#([\d.]+)#>", text)
    pieces = [(parts[i], float(parts[i + 1]) if i + 1 < len(parts) else 0.0) for i in range(0, len(parts), 2)]
    out, subs, cur = [], [], 0
    for t, gap in pieces:
        if not re.search(r"[\w㐀-鿿]", t):
            a = np.zeros(int(sr * 0.3), np.int16)
        else:
            a = _one(t, voice, instruction)
            loud = np.where(np.abs(a.astype(np.int32)) > 0.02 * 32768)[0]     # same trim rule as drama_tts.trim
            if len(loud):
                a = a[max(0, loud[0] - int(0.06 * sr)):loud[-1] + int(0.06 * sr)]
            subs.append({"text": t, "time_begin": round(cur * 1000 / sr), "time_end": round((cur + len(a)) * 1000 / sr)})
        out.append(a); cur += len(a)
        if gap:
            g = np.zeros(int(gap * sr), np.int16); out.append(g); cur += len(g)
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(np.concatenate(out).tobytes())
    Path(sub_path).write_text(json.dumps(subs, ensure_ascii=False))
    return sum(len(t) for t, _ in pieces)
