#!/usr/bin/env python3
"""Find the story's original Strand Magazine illustrations on Wikimedia Commons (public domain only),
download originals politely, and assign one to each scene by page position.

Usage: fetch_art.py <episode_dir>
Writes art/paget/NN-pgXXX.png|jpg, art/CREDITS.md; updates episode.json scenes[].art, art_credit, thumbnail_art.
Falls back to the generic Baker Street illustrations from episode 1 when nothing verifiable is found.
"""
import html, json, re, shutil, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

UA = {"User-Agent": "sleep-detective/0.2 (personal audio project; low request rate)"}
CAPTION = re.compile(r"^File:The Strand Magazine vol\. (\d+), no\. (\d+), pg\. (\d+) - (.+)\.(png|jpe?g)$", re.I)
FALLBACK = Path(__file__).resolve().parent.parent / "episodes" / "01-red-headed-league" / "art" / "paget"
PAGET_BOOKS = {"《福爾摩斯冒險史》", "《福爾摩斯回憶錄》", "《福爾摩斯歸來記》"}


def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"})
    for attempt in range(5):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        except (urllib.error.URLError, TimeoutError) as e:
            time.sleep(5 * (attempt + 1))
    raise SystemExit("commons api unreachable")


def fetch(url, target):
    for attempt in range(6):
        try:
            target.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read())
            return
        except urllib.error.HTTPError as e:
            wait = int(e.headers.get("Retry-After") or 0) or 20 * (attempt + 1)
            print(f"  HTTP {e.code} for {target.name}; waiting {wait}s", flush=True)
            time.sleep(min(wait, 900))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(15)
    raise SystemExit(f"could not download {url}")


def key(s):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"^(the|a|an)\s+", "", s.lower().replace("’", "'")))


def candidates(title_en):
    titles = set()
    for q in (f'"{title_en}" Strand Magazine', f"{title_en} Paget", f'"{title_en}" illustration',
              f'"{title_en}" Sherlock Holmes', f'"{title_en}" Steele'):
        r = api({"action": "query", "list": "search", "srsearch": q, "srnamespace": 6, "srlimit": 100})
        titles |= {s["title"] for s in r.get("query", {}).get("search", [])}
    rows = []
    titles = sorted(titles)
    for i in range(0, len(titles), 40):
        r = api({"action": "query", "titles": "|".join(titles[i:i + 40]), "prop": "imageinfo",
                 "iiprop": "url|size|extmetadata"})
        for p in r["query"]["pages"].values():
            ii = (p.get("imageinfo") or [{}])[0]
            md = {k: html.unescape(re.sub(r"<[^>]+>", " ", str(v.get("value", "")))).strip()
                  for k, v in ii.get("extmetadata", {}).items()}
            rows.append({"title": p["title"], "url": ii.get("url"), "w": ii.get("width"), "h": ii.get("height"),
                         "license": md.get("LicenseShortName", ""), "artist": re.sub(r"\s+", " ", md.get("Artist", "")),
                         "about": " ".join(md.get(k, "") for k in ("Categories", "ImageDescription", "ObjectName"))})
    return rows


def main():
    ep = Path(sys.argv[1]).expanduser()
    cfg = json.loads((ep / "episode.json").read_text())
    story = key(cfg["title_en"])
    rows = candidates(cfg["title_en"])
    picked = []
    for r in rows:
        m = CAPTION.match(r["title"])
        if not m or not r["license"].lower().startswith("public domain") or not r["url"]:
            continue
        if story not in key(r["about"]) and story not in key(m.group(4)):
            continue
        picked.append({**r, "vol": int(m.group(1)), "no": int(m.group(2)), "pg": int(m.group(3)), "caption": m.group(4)})
    # one magazine issue per story: keep the issue holding most matches
    if picked:
        issues = {}
        for p in picked:
            issues.setdefault((p["vol"], p["no"]), []).append(p)
        picked = sorted(max(issues.values(), key=len), key=lambda p: p["pg"])[:12]
    else:
        # other public-domain illustrations that name this story (e.g. Collier's, Frederic Dorr Steele); no page order
        picked = sorted([{**r, "caption": re.sub(r"^File:|\.[a-z]+$", "", r["title"])} for r in rows
                         if r["license"].lower().startswith("public domain") and r["url"]
                         and re.search(r"\.(png|jpe?g)$", r["url"], re.I) and (r["w"] or 0) >= 600
                         and story in key(r["title"] + " " + r["about"])], key=lambda r: r["title"])[:8]
    outdir = ep / "art" / "paget"
    outdir.mkdir(parents=True, exist_ok=True)
    credits = ["# 畫面素材出處（全部公版）", ""]
    if picked:
        for k, p in enumerate(picked, 1):
            ext = p["url"].rsplit(".", 1)[-1].lower()
            p["file"] = f"{k:02d}-pg{p['pg']}.{ext}" if "pg" in p else f"{k:02d}-art.{ext}"
            if not (outdir / p["file"]).exists():
                fetch(p["url"], outdir / p["file"])
                time.sleep(10)
            page = "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(p["title"].replace(" ", "_"))
            credits.append(f"- `{p['file']}`：{p['caption']}（{p['artist'] or '佚名'}，{p['license']}）— {page}")
        if "pg" in picked[0]:
            # a Strand page holds ~610 words of these stories (measured on two stories); the story starts on the first plate's page
            words = sum(len(r["en"].split()) for r in json.loads((ep / "script" / "script.json").read_text()))
            span = max(words / 610, picked[-1]["pg"] - picked[0]["pg"] + 1)
            for p in picked:
                p["frac"] = min((p["pg"] - picked[0]["pg"]) / span, 1.0)
        else:
            for k, p in enumerate(picked):
                p["frac"] = k / len(picked)
        artists = sorted({re.sub(r"\s*\(.*", "", p["artist"]).strip() for p in picked if p["artist"]} - {"The Strand Magazine"})
        if "pg" in picked[0]:
            # Commons credits these scans to the magazine; Paget drew every Strand plate for the first three books
            who = "Sidney Paget" if cfg.get("collection") in PAGET_BOOKS or cfg["number"] == 1 else "、".join(artists)
            cfg["art_credit"] = f"插畫：{who + '，' if who else ''}The Strand Magazine 原刊（公版）"
        else:
            cfg["art_credit"] = f"插畫：{'、'.join(artists) or '原刊插畫'}（公版）"
    else:
        for f in ("06-pg197.png", "01-pg190.png", "07-pg198.png"):
            shutil.copy(FALLBACK / f, outdir / f)
        picked = [{"file": "06-pg197.png", "frac": 0.0}]
        credits.append("- 找不到這一篇可驗證的公版原刊插畫；用第一集〈紅髮會〉的 Sidney Paget 插畫（1891，公版）代替")
        cfg["art_credit"] = "插畫：Sidney Paget（1891，公版）"
        cfg["art_fallback"] = True
    # scene position by cumulative text length, then the latest illustration at or before that point
    rows_zh = json.loads((ep / "script" / "script.json").read_text())
    lens = [len(r["zh"]) for r in rows_zh]
    total = sum(lens)
    pos = {r["id"]: sum(lens[:i]) / total for i, r in enumerate(rows_zh)}
    for s in cfg["scenes"]:
        f = pos[s["start"]]
        s["art"] = max((p for p in picked if p["frac"] <= f + 0.03), key=lambda p: p["frac"], default=picked[0])["file"]
    cfg["thumbnail_art"] = picked[min(1, len(picked) - 1)]["file"]
    (ep / "art" / "CREDITS.md").write_text("\n".join(credits) + "\n", encoding="utf-8")
    (ep / "episode.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{ep.name}: {len(picked)} illustrations{' (fallback)' if cfg.get('art_fallback') else ''}; "
          f"scenes → {[s['art'] for s in cfg['scenes']]}")


if __name__ == "__main__":
    main()
