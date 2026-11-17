#!/usr/bin/env python3
"""The whole Holmes canon as one ordered series, and extraction of each story into an episode folder.

Usage:
 series.py list
 series.py extract [N ...] # create episodes/NN-slug/{source,episode.json} (skips existing)

The four novels come after the 56 short stories. Each is cut at chapter boundaries into parts of about
9k English words (never inside a chapter); a part's episode.json carries novel/part/parts/chapters, and
translate.py gives every part but the last the "to be continued" outro.
"""
import json, re, sys
from pathlib import Path

import show

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "sources"
EPISODES = ROOT / "episodes"

COLL = {
    "adv": ("pg1661.txt", "《福爾摩斯冒險史》", "1891–1892"),
    "mem": ("pg834.txt", "《福爾摩斯回憶錄》", "1892–1893"),
    "ret": ("pg108.txt", "《福爾摩斯歸來記》", "1903–1904"),
    "bow": ("pg2350.txt", "《福爾摩斯最後致意》", "1908–1917"),
    "cas": ("pg69700.txt", "《福爾摩斯案簿錄》", "1921–1927"),
}

# (collection, heading line exactly as in the Gutenberg text, zh title, en title, narrator)
STORIES = [
    ("adv", "II. THE RED-HEADED LEAGUE", "紅髮會", "The Red-Headed League", "watson"),
    ("adv", "I. A SCANDAL IN BOHEMIA", "波希米亞醜聞", "A Scandal in Bohemia", "watson"),
    ("adv", "III. A CASE OF IDENTITY", "身分之謎", "A Case of Identity", "watson"),
    ("adv", "IV. THE BOSCOMBE VALLEY MYSTERY", "博斯科姆溪谷之謎", "The Boscombe Valley Mystery", "watson"),
    ("adv", "V. THE FIVE ORANGE PIPS", "五個橘籽", "The Five Orange Pips", "watson"),
    ("adv", "VI. THE MAN WITH THE TWISTED LIP", "歪嘴的男人", "The Man with the Twisted Lip", "watson"),
    ("adv", "VII. THE ADVENTURE OF THE BLUE CARBUNCLE", "藍寶石案", "The Blue Carbuncle", "watson"),
    ("adv", "VIII. THE ADVENTURE OF THE SPECKLED BAND", "花斑帶子", "The Speckled Band", "watson"),
    ("adv", "IX. THE ADVENTURE OF THE ENGINEER’S THUMB", "工程師的大拇指", "The Engineer's Thumb", "watson"),
    ("adv", "X. THE ADVENTURE OF THE NOBLE BACHELOR", "貴族單身漢", "The Noble Bachelor", "watson"),
    ("adv", "XI. THE ADVENTURE OF THE BERYL CORONET", "綠玉皇冠", "The Beryl Coronet", "watson"),
    ("adv", "XII. THE ADVENTURE OF THE COPPER BEECHES", "銅山毛櫸", "The Copper Beeches", "watson"),
    ("mem", "I. Silver Blaze", "銀色馬", "Silver Blaze", "watson"),
    ("mem", "II. The Adventure of the Cardboard Box", "硬紙盒子", "The Cardboard Box", "watson"),
    ("mem", "III. The Yellow Face", "黃色的臉", "The Yellow Face", "watson"),
    ("mem", "IV. The Stockbroker’s Clerk", "股票經紀人的書記員", "The Stockbroker's Clerk", "watson"),
    ("mem", "V. The “Gloria Scott”", "格洛里亞斯科特號", "The Gloria Scott", "watson"),
    ("mem", "VI. The Musgrave Ritual", "馬斯格雷夫禮典", "The Musgrave Ritual", "watson"),
    ("mem", "VII. The Reigate Squires", "賴蓋特之謎", "The Reigate Squires", "watson"),
    ("mem", "VIII. The Crooked Man", "駝背人", "The Crooked Man", "watson"),
    ("mem", "IX. The Resident Patient", "住院的病人", "The Resident Patient", "watson"),
    ("mem", "X. The Greek Interpreter", "希臘譯員", "The Greek Interpreter", "watson"),
    ("mem", "XI. The Naval Treaty", "海軍協定", "The Naval Treaty", "watson"),
    ("mem", "XII. The Final Problem", "最後一案", "The Final Problem", "watson"),
    ("ret", "THE ADVENTURE OF THE EMPTY HOUSE", "空屋", "The Empty House", "watson"),
    ("ret", "THE ADVENTURE OF THE NORWOOD BUILDER", "諾伍德的建築師", "The Norwood Builder", "watson"),
    ("ret", "THE ADVENTURE OF THE DANCING MEN", "跳舞的人", "The Dancing Men", "watson"),
    ("ret", "THE ADVENTURE OF THE SOLITARY CYCLIST", "孤身騎車人", "The Solitary Cyclist", "watson"),
    ("ret", "THE ADVENTURE OF THE PRIORY SCHOOL", "修道院公學", "The Priory School", "watson"),
    ("ret", "THE ADVENTURE OF BLACK PETER", "黑彼得", "Black Peter", "watson"),
    ("ret", "THE ADVENTURE OF CHARLES AUGUSTUS MILVERTON", "米爾沃頓", "Charles Augustus Milverton", "watson"),
    ("ret", "THE ADVENTURE OF THE SIX NAPOLEONS", "六座拿破崙半身像", "The Six Napoleons", "watson"),
    ("ret", "THE ADVENTURE OF THE THREE STUDENTS", "三個學生", "The Three Students", "watson"),
    ("ret", "THE ADVENTURE OF THE GOLDEN PINCE-NEZ", "金邊夾鼻眼鏡", "The Golden Pince-Nez", "watson"),
    ("ret", "THE ADVENTURE OF THE MISSING THREE-QUARTER", "失蹤的中衛", "The Missing Three-Quarter", "watson"),
    ("ret", "THE ADVENTURE OF THE ABBEY GRANGE", "格蘭其莊園", "The Abbey Grange", "watson"),
    ("ret", "THE ADVENTURE OF THE SECOND STAIN", "第二塊血跡", "The Second Stain", "watson"),
    ("bow", "The Adventure of Wisteria Lodge", "紫藤居", "Wisteria Lodge", "watson"),
    ("bow", "The Adventure of the Bruce-Partington Plans", "布魯斯—帕廷頓計畫", "The Bruce-Partington Plans", "watson"),
    ("bow", "The Adventure of the Devil’s Foot", "魔鬼之足", "The Devil's Foot", "watson"),
    ("bow", "The Adventure of the Red Circle", "紅圈會", "The Red Circle", "watson"),
    ("bow", "The Disappearance of Lady Frances Carfax", "法蘭西絲女士失蹤案", "Lady Frances Carfax", "watson"),
    ("bow", "The Adventure of the Dying Detective", "垂死的偵探", "The Dying Detective", "watson"),
    ("bow", "His Last Bow: The War Service of Sherlock Holmes", "最後致意", "His Last Bow", "third"),
    ("cas", "THE ADVENTURE OF THE ILLUSTRIOUS CLIENT", "顯貴的主顧", "The Illustrious Client", "watson"),
    ("cas", "THE ADVENTURE OF THE BLANCHED SOLDIER", "皮膚變白的軍人", "The Blanched Soldier", "holmes"),
    ("cas", "THE ADVENTURE OF THE MAZARIN STONE", "馬薩林寶石", "The Mazarin Stone", "third"),
    ("cas", "THE ADVENTURE OF THE THREE GABLES", "三角牆山莊", "The Three Gables", "watson"),
    ("cas", "THE ADVENTURE OF THE SUSSEX VAMPIRE", "薩塞克斯吸血鬼", "The Sussex Vampire", "watson"),
    ("cas", "THE ADVENTURE OF THE THREE GARRIDEBS", "三個同姓的人", "The Three Garridebs", "watson"),
    ("cas", "THE PROBLEM OF THOR BRIDGE", "雷神橋之謎", "The Problem of Thor Bridge", "watson"),
    ("cas", "THE ADVENTURE OF THE CREEPING MAN", "爬行人", "The Creeping Man", "watson"),
    ("cas", "THE ADVENTURE OF THE LION'S MANE", "獅鬃毛", "The Lion's Mane", "holmes"),
    ("cas", "THE ADVENTURE OF THE VEILED LODGER", "戴面紗的房客", "The Veiled Lodger", "watson"),
    ("cas", "THE ADVENTURE OF SHOSCOMBE OLD PLACE", "肖斯科姆古宅", "Shoscombe Old Place", "watson"),
    ("cas", "THE ADVENTURE OF THE RETIRED COLOURMAN", "退休的顏料商", "The Retired Colourman", "watson"),
]

# (Gutenberg file, zh title, en title, narrator); chapter headings are found in the file itself
NOVELS = [
    ("pg244.txt", "血字的研究", "A Study in Scarlet", "watson"),
    ("pg2097.txt", "四簽名", "The Sign of the Four", "watson"),
    ("pg2852.txt", "巴斯克維爾的獵犬", "The Hound of the Baskervilles", "watson"),
    ("pg3289.txt", "恐怖谷", "The Valley of Fear", "watson"),
]
PART_WORDS = 9000
ZH_NUM = "一二三四五六七八九十"

END_MARK = re.compile(r"^\*\*\* END OF (THE|THIS) PROJECT GUTENBERG", re.I)
# section markers inside a story ("I.", "PART II", "Chapter …") are dropped; the scene outline handles pacing
SECTION = re.compile(r"^(PART\s+[IVX]+\.?|[IVX]+\.|CHAPTER\s+[IVX\d]+\.?.*)$", re.I)


def slug(en):
    s = re.sub(r"[^a-z0-9]+", "-", en.lower()).strip("-")
    return re.sub(r"^(the|a|an)-", "", s)


def episodes():
    for n, (coll, head, zh, en, narrator) in enumerate(STORIES, 1):
        yield {"number": n, "coll": coll, "heading": head, "title": zh, "title_en": en, "narrator": narrator,
               "dir": EPISODES / f"{n:02d}-{slug(en)}"}
    n = len(STORIES)
    for fname, zh, en, narrator in NOVELS:
        chs, parts = novel_chapters(fname), novel_parts(fname)
        for k, (a, b) in enumerate(parts, 1):
            n += 1
            yield {"number": n, "novel": zh, "novel_en": en, "part": k, "parts": len(parts),
                   "chapters": [t for t, *_ in chs[a:b]], "chapter_range": [a, b],
                   "title": f"{zh}（{ZH_NUM[k - 1]}）", "title_en": f"{en}, Part {k}", "narrator": narrator,
                   "dir": EPISODES / f"{n:02d}-{slug(en)}-{k}"}


CHAPTER = re.compile(r"^(CHAPTER|Chapter)\s+([IVXLC]+|\d+)\.?$")
PART = re.compile(r"^PART\s+[IVX]+\.?$")


def paragraphs(lines):
    paras = []
    for p in re.split(r"\n\s*\n", "\n".join(lines)):
        t = re.sub(r"\s+", " ", p).strip()
        if not t or SECTION.match(t) or t.upper() in ("THE END",) or t.startswith("[Illustration"):
            continue
        paras.append(t.replace("_", ""))
    return paras


def novel_chapters(fname):
    """[(chapter title, [paragraphs], book part)] in book order. Headings count only at column 0 (the tables
 of contents are indented or carry the title on the same line); PART lines and their subtitle are dropped."""
    lines = (SOURCES / fname).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    marks = [i for i, l in enumerate(lines) if CHAPTER.match(l) or l == "Epilogue" or PART.match(l)
             or END_MARK.match(l.strip())]
    out, book_part = [], 0
    for a, b in zip(marks, marks[1:]):
        if PART.match(lines[a]):
            book_part += 1
            continue
        if END_MARK.match(lines[a].strip()):
            continue
        body = lines[a + 1:b]
        title = "Epilogue"
        if lines[a] != "Epilogue":
            j = next(j for j, l in enumerate(body) if l.strip())
            title, body = body[j].strip().strip("_").rstrip("."), body[j + 1:]
        out.append((title, paragraphs(body), book_part))
    return out


def novel_parts(fname):
    """[(first, last+1)] chapter ranges. Whole chapters only, never across the book's own PART I/II line,
 and the number of cuts is free: minimise the summed squared distance of each part from PART_WORDS."""
    chs = novel_chapters(fname)
    words = [sum(len(p.split()) for p in ps) for _, ps, _ in chs]
    best, back = [0.0] + [float("inf")] * len(chs), [0] * (len(chs) + 1)
    for i in range(1, len(chs) + 1):
        for j in range(i):
            if chs[j][2] != chs[i - 1][2]:
                continue
            cost = best[j] + (sum(words[j:i]) - PART_WORDS) ** 2
            if cost < best[i]:
                best[i], back[i] = cost, j
    ranges, i = [], len(chs)
    while i:
        ranges.append((back[i], i))
        i = back[i]
    return ranges[::-1]


def part_paragraphs(ep):
    fname = next(f for f, zh, *_ in NOVELS if zh == ep["novel"])
    a, b = ep["chapter_range"]
    return [p for _, ps, _ in novel_chapters(fname)[a:b] for p in ps]


def story_paragraphs(coll, heading):
    fname = COLL[coll][0]
    lines = (SOURCES / fname).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    heads = [h for c, h, *_ in STORIES if c == coll]
    norm = lambda l: l.strip().replace("_", "")   # italic markers: V. The “_Gloria Scott_”
    idx = [i for i, l in enumerate(lines) if norm(l) == heading]
    if not idx:
        raise SystemExit(f"heading not found: {heading!r} in {fname}")
    start = idx[-1]                       # the table of contents comes first; the real heading is the last match
    later = [i for i, l in enumerate(lines) if i > start and (norm(l) in heads and norm(l) != heading
                                                              or END_MARK.match(l.strip()))]
    end = min(later) if later else len(lines)
    return paragraphs(lines[start + 1:end])


def extract(ep, base_voice):
    d = ep["dir"]
    if (d / "episode.json").exists():
        return "exists"
    paras = part_paragraphs(ep) if "novel" in ep else story_paragraphs(ep["coll"], ep["heading"])
    (d / "source").mkdir(parents=True, exist_ok=True)
    (d / "source" / f"{slug(ep['title_en'])}.en.txt").write_text("\n\n".join(paras) + "\n", encoding="utf-8")
    if "novel" in ep:
        coll_zh, phrase = f"《{ep['novel']}》", f"長篇《{ep['novel']}》的第{ZH_NUM[ep['part'] - 1]}夜"
    else:
        coll_zh = COLL[ep["coll"]][1]
        phrase = f"{coll_zh}裡的〈{ep['title']}〉"
    cfg = {"number": ep["number"], "title": ep["title"], "title_en": ep["title_en"], "series": "福爾摩斯睡前故事",
           "channel_working_name": show.CHANNEL, "collection": coll_zh, "narrator": ep["narrator"],
           "voice": base_voice, "source_phrase": phrase,
           "gaps": {"paragraph_s": 1.5, "scene_s": 3.5, "after_intro_s": 3.0, "before_outro_s": 4.0},
           "status": "extracted"}
    if "novel" in ep:
        cfg.update({k: ep[k] for k in ("novel", "part", "parts", "chapters", "chapter_range")})
    (d / "episode.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    words = sum(len(p.split()) for p in paras)
    return f"{len(paras)} paragraphs, {words} words"


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    first = next(episodes())["dir"] / "episode.json"
    base_voice = json.loads(first.read_text())["voice"] if first.exists() else None
    want = {int(a) for a in sys.argv[2:]}
    for ep in episodes():
        if want and ep["number"] not in want:
            continue
        if cmd == "list":
            extra = f"  {len(ep['chapters'])} ch: {ep['chapters'][0]} … {ep['chapters'][-1]}" if "novel" in ep else ""
            print(ep["number"], ep["title"], ep["title_en"], ep["narrator"], ep["dir"].name + extra)
        elif cmd == "extract":
            print(ep["number"], ep["dir"].name, extract(ep, base_voice))


if __name__ == "__main__":
    main()
