#!/usr/bin/env python3
"""Draft the YouTube upload text (title, description with chapters, tags). Publishing stays manual.

Usage: package.py <episode_dir>
"""
import re, json, sys
from pathlib import Path
import show, season

DIGIT = "〇一二三四五六七八九"
NOVEL_YEAR = {"血字的研究": "1887", "四簽名": "1890", "巴斯克維爾的獵犬": "1901–1902", "恐怖谷": "1914–1915"}


def zh_num(n):
    """1–99 in Chinese words: 七, 十二, 二十, 三十四."""
    tens, ones = divmod(n, 10)
    return (DIGIT[tens] if tens > 1 else "") + ("十" if tens else "") + (DIGIT[ones] if ones or not tens else "")


def year_of(cfg):
    if cfg.get("novel"):
        return NOVEL_YEAR.get(cfg["novel"], "公版")
    from series import COLL
    return next((y for _, zh, y in COLL.values() if zh == cfg.get("collection")), "公版")


def main():
    ep = Path(sys.argv[1]).expanduser()
    cfg = json.loads((ep / "episode.json").read_text())
    chapters = (ep / "build" / "chapters.txt").read_text(encoding="utf-8").strip()
    night = f"第{zh_num(show.night(cfg))}夜"
    rampo = cfg.get("author") == "江戶川亂步"          # season 2
    # the cover's hook leads the title too (covers/hooks.json "big", 「只要紅頭髮|週薪四英鎊？」)
    hooks = json.loads((ep.parent.parent / "covers" / "hooks.json").read_text()).get("big", {}) \
        if (ep.parent.parent / "covers" / "hooks.json").exists() else {}
    hook = hooks.get(str(cfg["number"]))
    if hook:
        a, b = (hook.split("|") + [""])[:2]
        hook = a + ("，" if len(a) >= 4 and len(b) >= 4 and a[-1] not in "的張那這" else "") + b
        who = season.of(cfg)["who"]
        title = f"{hook}｜{who}〈{cfg['title']}〉廣播劇完整版｜助眠推理故事・第{show.night(cfg)}夜"
    else:
        title = f"{cfg['series']}｜{cfg['title']}（完整版）｜大人的助眠推理故事｜{night}"
    desc = f"""今晚的故事，是{cfg['source_phrase']}。
{re.sub(r'<#[\d.]+#>', '', cfg.get('teaser', ''))}
福爾摩斯、華生與每位登場人物都有自己的聲音；故事節奏緩慢，驚險的地方都放輕了，結尾一定解謎。建議戴上耳機、把燈調暗，聽到睡著也沒關係。

章節
{chapters}

—
・旁白與各角色配音皆為 AI 語音合成（分角色廣播劇）
・故事改編自柯南·道爾（Arthur Conan Doyle）〈{cfg['title_en']}〉（{year_of(cfg)}，公版）；中文稿由本頻道自英文原著翻譯改寫
・插畫：《The Strand Magazine》等原刊插畫（公版）
・本影片不是為兒童打造的內容

#睡前故事 #助眠 #福爾摩斯 #推理故事 #有聲書"""
    if rampo:
        return rampo_text(ep, cfg, title, chapters)
    if cfg.get("author") in SEASON_TEXT:      # seasons 3 (Christie) and 4 (Father Brown)
        return season_text(ep, cfg, title, chapters)
    tags = ["睡前故事", "助眠", "福爾摩斯", "福尔摩斯", cfg["title"], "推理故事", "偵探故事", "有聲書",
            "大人的睡前故事", "失眠", "sleep story", "Sherlock Holmes", cfg["title_en"]]
    write(ep, title, desc, tags)


def rampo_text(ep, cfg, title, chapters):
    script = (ep / "script" / "script-zh.md").read_text(encoding="utf-8")
    akechi = "明智" in script
    works = "、".join(f"〈{w['ja']}〉（{w['year']}）" for w in cfg["works"])
    desc = f"""今晚的故事，是{cfg['source_phrase']}。
{re.sub(r'<#[\d.]+#>', '', cfg.get('teaser', ''))}
{"明智小五郎與" if akechi else ""}每位登場人物都有自己的聲音；故事節奏緩慢，驚險的地方都放輕了，結尾一定解謎。建議戴上耳機、把燈調暗，聽到睡著也沒關係。

章節
{chapters}

—
・旁白與各角色配音皆為 AI 語音合成（分角色廣播劇）
・故事改編自江戶川亂步{works}，公版；中文稿由本頻道自日文原著（青空文庫）翻譯改寫
・{cfg.get('art_credit', '插畫：本頻道以 AI 繪製')}
・本影片不是為兒童打造的內容

#睡前故事 #助眠 #江戶川亂步 #{'明智小五郎 #' if akechi else ''}推理故事 #有聲書"""
    tags = ["睡前故事", "助眠", "江戶川亂步", "江户川乱步", *(["明智小五郎"] if akechi else []), cfg["title"],
            *(w["ja"] for w in cfg["works"]), "推理故事", "日本推理", "偵探故事", "有聲書", "大人的睡前故事", "失眠",
            "sleep story", "Edogawa Rampo"]
    write(ep, title, desc, tags)


DETECTIVE = {"poirot": ("白羅", "Hercule Poirot"), "marple": ("瑪波小姐", "Miss Marple"), "quin": ("奎因先生", "Harley Quin"),
             "brown": ("布朗神父", "Father Brown"), "lupin": ("亞森·羅蘋", "Arsène Lupin"),
             "huosang": ("霍桑", "Huo Sang"), "oldman": ("角落裡的老人", "The Old Man in the Corner"),
             "cuff": ("卡夫警長", "Sergeant Cuff"), "vance": ("菲洛·凡斯", "Philo Vance"),
             "hanshichi": ("半七", "Hanshichi"), "umon": ("沉默的右門", "Umon"),
             "raffles": ("萊佛士", "A. J. Raffles"), "trent": ("特倫特", "Philip Trent"),
             "gillingham": ("吉林漢", "Antony Gillingham"),
             "loveday": ("洛芙黛·布魯克", "Loveday Brooke"), "dorcas": ("多卡絲·丁恩", "Dorcas Dene"),
             "hilda": ("希爾達·韋德", "Hilda Wade"), "molly": ("茉莉夫人", "Lady Molly"), "violet": ("薇奧莉·斯特蘭奇", "Violet Strange"),
             "di": ("狄公", "Judge Dee"), "bao": ("包公", "Judge Bao"), "lan": ("藍鼎元", "Lan Dingyuan"),
             "lecoq": ("勒寇克", "Monsieur Lecoq")}
SEASON_TEXT = {
    "阿嘉莎·克莉絲蒂": {"credit": "阿嘉莎·克莉絲蒂（Agatha Christie）", "pd": "台灣與美國公版", "hash": "阿嘉莎克莉絲蒂",
                  "tags": ["阿嘉莎", "阿嘉莎·克莉絲蒂", "克莉絲蒂"], "en": "Agatha Christie"},
    "莫里斯·盧布朗": {"credit": "莫里斯·盧布朗（Maurice Leblanc）", "pd": "公版", "hash": "亞森羅蘋",
                 "tags": ["亞森羅蘋", "亞森·羅蘋", "怪盜紳士", "莫里斯·盧布朗"], "en": "Maurice Leblanc"},
    "程小青": {"credit": "程小青", "pd": "台灣公版", "hash": "霍桑探案",
            "tags": ["霍桑探案", "程小青", "東方福爾摩斯", "民國偵探小說"], "en": "Cheng Xiaoqing"},
    "岡本綺堂": {"credit": "岡本綺堂", "pd": "公版", "hash": "半七捕物帳",
             "tags": ["半七捕物帳", "岡本綺堂", "捕物帳", "江戶推理", "時代推理"], "en": "Okamoto Kido"},
    "佐佐木味津三": {"credit": "佐佐木味津三", "pd": "台灣與美國公版", "hash": "右門捕物帖",
               "tags": ["右門捕物帖", "佐佐木味津三", "捕物帳", "江戶推理", "時代推理"], "en": "Sasaki Mitsuzo"},
    "洪農": {"credit": "洪農（E. W. Hornung）", "pd": "公版", "hash": "紳士怪盜萊佛士",
           "tags": ["萊佛士", "紳士怪盜", "洪農", "怪盜推理"], "en": "E. W. Hornung"},
    "本特利": {"credit": "本特利（E. C. Bentley）", "pd": "公版", "hash": "特倫特最後一案",
            "tags": ["特倫特最後一案", "本特利", "黃金時代推理"], "en": "E. C. Bentley"},
    "米恩": {"credit": "米恩（A. A. Milne）", "pd": "公版", "hash": "紅屋之謎",
           "tags": ["紅屋之謎", "米恩", "小熊維尼作者", "黃金時代推理"], "en": "A. A. Milne"},
    "女偵探合輯": {"credit": "皮爾吉斯、西姆斯、格蘭特·艾倫、奧希茲、安娜·凱瑟琳·格林", "pd": "公版", "hash": "女偵探",
              "tags": ["女偵探", "維多利亞推理", "女性偵探", "經典推理"], "en": "Victorian & Edwardian women detectives"},
    "加博里歐": {"credit": "加博里歐（Émile Gaboriau）", "pd": "公版", "hash": "勒寇克",
              "tags": ["勒寇克", "加博里歐", "法國推理", "偵探小說之父"], "en": "Émile Gaboriau"},
    "中國公案": {"credit": "清代《武則天四大奇案》、明代《龍圖公案》、藍鼎元《鹿洲公案》", "pd": "公版", "hash": "中國公案",
             "tags": ["狄公案", "包公案", "鹿洲公案", "公案小說", "中國偵探故事", "狄仁傑", "包青天"], "en": "Chinese gong'an classics"},
    "威爾基·柯林斯": {"credit": "威爾基·柯林斯（Wilkie Collins）", "pd": "公版", "hash": "月光石",
                "tags": ["月光石", "威爾基·柯林斯", "第一部長篇推理小說", "維多利亞推理"], "en": "Wilkie Collins"},
    "范·達因": {"credit": "范·達因（S. S. Van Dine）", "pd": "公版", "hash": "菲洛凡斯",
             "tags": ["菲洛·凡斯", "范·達因", "范達因", "黃金時代推理"], "en": "S. S. Van Dine"},
    "奧希茲": {"credit": "奧希茲女男爵（Baroness Orczy）", "pd": "公版", "hash": "角落裡的老人",
            "tags": ["角落裡的老人", "奧希茲", "安樂椅神探", "安樂椅偵探"], "en": "Baroness Orczy"},
    "卻斯特頓": {"credit": "卻斯特頓（G. K. Chesterton）", "pd": "公版", "hash": "卻斯特頓",
              "tags": ["卻斯特頓", "切斯特頓", "布朗神父探案"], "en": "G. K. Chesterton"},
}


def season_text(ep, cfg, title, chapters):
    zh, en = DETECTIVE[cfg["detective"]]
    st = SEASON_TEXT[cfg["author"]]
    ja = cfg.get("source_lang") == "ja"     # 半七／右門 have works[] instead of book_en/year (KeyError stopped 411–420)
    ja_src = f"故事改編自{st['credit']}《{cfg['collection'].strip('《》')}》〈{cfg['works'][0]['ja']}〉（{st['pd']}）；中文稿由本頻道自日文原著翻譯改寫" if ja else ""
    desc = f"""今晚的故事，是{cfg['source_phrase']}。
{re.sub(r'<#[\d.]+#>', '', cfg.get('teaser', ''))}
{zh}與每位登場人物都有自己的聲音；故事節奏緩慢，驚險的地方都放輕了，結尾一定解謎。建議戴上耳機、把燈調暗，聽到睡著也沒關係。

章節
{chapters}

—
・旁白與各角色配音皆為 AI 語音合成（分角色廣播劇）
・{ja_src if ja else f"故事出自{st['credit']}〈{cfg['title']}〉（{cfg['year']}，{st['pd']}）；依中文原著朗讀，只調整少數不利聆聽的字詞" if cfg.get("source_lang") == "zh" else f"故事改編自{st['credit']}《{cfg['book_en']}》（{cfg['year']}，{st['pd']}）；中文稿由本頻道自{'法' if cfg.get('source_lang') == 'fr' else '英'}文原著翻譯改寫"}
・{cfg.get('art_credit', '插畫：本頻道以 AI 繪製')}
・本影片不是為兒童打造的內容

#睡前故事 #助眠 #{st['hash']} #{zh} #推理故事 #有聲書"""
    tags = ["睡前故事", "助眠", *st["tags"], zh, cfg["title"], cfg["collection"].strip("《》"),
            "推理故事", "偵探故事", "有聲書", "大人的睡前故事", "失眠", "sleep story", st["en"], en,
            cfg["works"][0]["ja"] if ja else cfg["book_en"]]
    write(ep, title, desc, tags)


def write(ep, title, desc, tags):
    out = ep / "upload"
    out.mkdir(exist_ok=True)
    (out / "title.txt").write_text(title + "\n", encoding="utf-8")
    (out / "description.txt").write_text(desc + "\n", encoding="utf-8")
    (out / "tags.txt").write_text(", ".join(tags) + "\n", encoding="utf-8")
    (out / "CHECKLIST.md").write_text(
        "# 上架前（製作者親手）\n\n"
        "- [ ] 旁白改用國際站或其他可對外營利的來源重新生成（中國站協議 §3.16）\n"
        "- [ ] （選擇性）你做的聲景與配樂\n"
        "- [ ] 受眾：選「不是為兒童打造」\n"
        "- [ ] 字幕：上傳 `build/zh-Hant.srt`（繁體）與 `build/zh-Hans.srt`（簡體）\n"
        "- [ ] 縮圖：`covers/final/NN.jpg`（完成影片資料夾裡同名 .jpg）\n"
        "- [ ] 按發佈\n", encoding="utf-8")
    print(title, len(title), "chars")


if __name__ == "__main__":
    main()
