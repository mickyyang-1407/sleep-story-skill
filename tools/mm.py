"""Shared MiniMax helpers. The key comes from the environment (MINIMAX_API_KEY, see .env.example) and is never written anywhere."""
import json, os, re, time, urllib.error, urllib.request

KEY = os.environ.get("MINIMAX_API_KEY", "").strip()      # [share export] reader's own key
HOST = os.environ.get("MINIMAX_HOST", "https://api.minimaxi.com")


def call(method, url, body=None, *, timeout=300, headers=None, retries=5):
    if not KEY:
        raise SystemExit("MINIMAX_API_KEY is not set (copy .env.example to .env and load it)")
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    h.update(headers or {})
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, method=method, headers=h,
                                         data=json.dumps(body).encode() if body is not None else None)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last = RuntimeError(f"HTTP {e.code}: {e.read()[:300]!r}")
            if e.code not in (429, 500, 502, 503, 504):
                raise last
        except OSError as e:  # timeouts, SSL handshake, dropped connections
            last = e
        time.sleep(min(30, 3 * 2 ** attempt))
    raise last


def fetch_bytes(url, timeout=120, retries=5):
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except OSError as e:
            last = e
            time.sleep(min(30, 3 * 2 ** attempt))
    raise last


def quota():
    # [share export] the remains endpoint only exists for a MiniMax (China) Token Plan; SD_QUOTA_FLOOR=0 skips it
    if os.environ.get("SD_QUOTA_FLOOR", "") == "0":
        return {"checked": False, "note": "quota not queried (SD_QUOTA_FLOOR=0)"}
    q = call("GET", "https://www.minimaxi.com/v1/token_plan/remains", timeout=60)
    g = next(b for b in q["model_remains"] if b["model_name"] == "general")
    return {"5h": g["current_interval_remaining_percent"], "weekly": g["current_weekly_remaining_percent"],
            "at": time.strftime("%Y-%m-%d %H:%M:%S")}


# Measured on episode 79 (D坂, ja→zh, 146 paragraphs) against a full human
# review (~40 real errors in the M3 draft): as TRANSLATOR 3.1 Flash broke 40 paragraphs into lines (310 newlines),
# leaked 15 simplified characters, split single speeches into several 「」 (17 quote mismatches vs 13) and made new
# meaning errors while fixing others — so M3 keeps translating. As SELF-CHECKER (effort medium) it caught 15 of the ~40
# (M3 flagged 2), so it checks. Human review stays mandatory either way.
# MiniMax-M3.1-Flash (GA; the Preview id is gone from /v1/models) for
# every call. The translator finding above was measured on the Preview; translation is done for all seasons but
# 764 (Claude, 11/06). SD_M3_MODEL=MiniMax-M3 brings the old translator back for a one-off.
M3_MODEL = os.environ.get("SD_M3_MODEL", "MiniMax-M3.1-Flash")
CHECK_MODEL = os.environ.get("SD_CHECK_MODEL", "MiniMax-M3.1-Flash")
DEADLINE = 900          # seconds for one m3 call before it is dropped and retried
# M3.1 Flash cannot turn thinking off, and by default spent 8–40k tokens thinking per call (a whole story took
# 40+ minutes and hit max_tokens with no text). Adaptive thinking at low effort: ~40 thinking tokens, 10 paragraphs 55 s.
M3_EFFORT = os.environ.get("SD_M3_EFFORT", "low")


def m3(system, user, *, max_tokens=40000, retries=8, model=None, effort=None):     # room for M3.1 Flash thinking + the text
    """Streamed (M3.1 Flash thinks before it writes; a non-streamed call on a whole story was cut off by the
 server with RemoteDisconnected five times running — a stream keeps bytes flowing). Returns (text, usage, stop)."""
    model = model or M3_MODEL
    extra = {"thinking": {"type": "adaptive"}, "output_config": {"effort": effort or M3_EFFORT}} if "M3.1" in model else {}
    body = json.dumps({"model": model, "max_tokens": max_tokens, "system": system, "stream": True, **extra,
                       "messages": [{"role": "user", "content": user}]}).encode()
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "anthropic-version": "2023-06-01"}
    last = None
    for attempt in range(retries):
        text, usage, stop = [], {}, None
        try:
            req = urllib.request.Request(f"{HOST}/anthropic/v1/messages", method="POST", headers=h, data=body)
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=300) as r:     # timeout = longest silence between chunks
                for raw in r:
                    if time.time() - t0 > DEADLINE:       # a stream that trickles forever never trips timeout=
                        raise TimeoutError(f"m3 stream over {DEADLINE}s")
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    ev = json.loads(line[5:].strip() or "{}")
                    t = ev.get("type")
                    if t == "content_block_delta" and ev["delta"].get("type") == "text_delta":
                        text.append(ev["delta"]["text"])
                    elif t == "message_start":
                        usage.update(ev["message"].get("usage", {}))
                    elif t == "message_delta":
                        stop = ev.get("delta", {}).get("stop_reason") or stop
                        usage.update(ev.get("usage", {}))
                    elif t == "error":
                        raise RuntimeError(f"stream error: {ev.get('error')}")
            return "".join(text), usage, stop
        except urllib.error.HTTPError as e:
            last = RuntimeError(f"HTTP {e.code}: {e.read()[:300]!r}")
            if e.code not in (429, 500, 502, 503, 504) or "1026" in str(last):   # the content filter never relents
                raise last
        except OSError as e:
            last = e
        time.sleep(min(60, 3 * 2 ** attempt))          # DNS dropped out for minutes once
    raise last
