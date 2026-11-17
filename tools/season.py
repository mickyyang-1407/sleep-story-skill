"""What differs between the seasons, in one place (, when season 3 arrived). Keyed by episode.json "author";
Holmes episodes have no author field. Folder numbers run on across the channel (Holmes 1–78, Rampo 79–102,
Christie 103–170); viewers see each season's own 第N夜."""

SEASONS = {
    None: {"label": "", "who": "福爾摩斯", "first": 1,
           "playlist": {"music": "福爾摩斯睡前故事｜枕邊偵探社", "nomusic": "福爾摩斯睡前故事｜枕邊偵探社（無配樂版）"}},
    "江戶川亂步": {"label": "亂步", "who": "江戶川亂步", "first": 79, "gate": "RAMPO-APPROVED.txt",
              "playlist": {"music": "江戶川亂步睡前故事｜枕邊偵探社", "nomusic": "江戶川亂步睡前故事｜枕邊偵探社（無配樂版）"}},
    #
    "阿嘉莎·克莉絲蒂": {"label": "阿嘉莎", "who": "阿嘉莎", "first": 103, "gate": "CHRISTIE-APPROVED.txt",
                  "not_before": (2027, 1, 1),
                  "playlist": {"music": "阿嘉莎睡前故事｜枕邊偵探社", "nomusic": "阿嘉莎睡前故事｜枕邊偵探社（無配樂版）"}},
    # public domain everywhere (Chesterton †1936, books 1911–1927)
    "卻斯特頓": {"label": "布朗神父", "who": "布朗神父", "first": 171, "gate": "BROWN-APPROVED.txt",
              "playlist": {"music": "布朗神父睡前故事｜枕邊偵探社", "nomusic": "布朗神父睡前故事｜枕邊偵探社（無配樂版）"}},
    # Leblanc †1941, books 1907–1929: public domain everywhere
    "莫里斯·盧布朗": {"label": "羅蘋", "who": "亞森·羅蘋", "first": 211, "gate": "LUPIN-APPROVED.txt",
                 "playlist": {"music": "亞森·羅蘋睡前故事｜枕邊偵探社", "nomusic": "亞森·羅蘋睡前故事｜枕邊偵探社（無配樂版）"}},
    # Chinese original, no translation; 程小青 †1976 → Taiwan
    # public domain from 2027-01-01 (same day as Christie)
    "程小青": {"label": "霍桑", "who": "霍桑", "first": 309, "gate": "HUOSANG-APPROVED.txt", "not_before": (2027, 1, 1),
            "playlist": {"music": "霍桑探案睡前故事｜枕邊偵探社", "nomusic": "霍桑探案睡前故事｜枕邊偵探社（無配樂版）"}},
    # — four more seasons (folder blocks 代決)
    "岡本綺堂": {"label": "半七", "who": "半七", "first": 386, "gate": "HANSHICHI-APPROVED.txt",
             "playlist": {"music": "半七捕物帳睡前故事｜枕邊偵探社", "nomusic": "半七捕物帳睡前故事｜枕邊偵探社（無配樂版）"}},
    "奧希茲": {"label": "角落裡的老人", "who": "角落裡的老人", "first": 436, "gate": "OLDMAN-APPROVED.txt",
            "playlist": {"music": "角落裡的老人睡前故事｜枕邊偵探社", "nomusic": "角落裡的老人睡前故事｜枕邊偵探社（無配樂版）"}},
    "威爾基·柯林斯": {"label": "月光石", "who": "月光石", "first": 486, "gate": "MOONSTONE-APPROVED.txt",
                "playlist": {"music": "月光石睡前故事｜枕邊偵探社", "nomusic": "月光石睡前故事｜枕邊偵探社（無配樂版）"}},
    #
    # qwen_art 用 ANIME_STYLE、art.py 保留彩色不上暖棕色調
    "范·達因": {"label": "菲洛·凡斯", "who": "菲洛·凡斯", "first": 506, "gate": "VANCE-APPROVED.txt", "art": "anime90s",
             "playlist": {"music": "菲洛·凡斯睡前故事｜枕邊偵探社", "nomusic": "菲洛·凡斯睡前故事｜枕邊偵探社（無配樂版）"}},
    # 右門捕物帖 — 佐々木味津三 †1934; the 20 stories used ran in 《冨士》 from 1928, exact months unproven, at the
    # latest 1931 → US public domain from 2027-01-01 at the latest, so nothing airs before then
    "佐佐木味津三": {"label": "右門", "who": "右門", "first": 611, "gate": "UMON-APPROVED.txt", "not_before": (2027, 1, 1),
                "playlist": {"music": "右門捕物帖睡前故事｜枕邊偵探社", "nomusic": "右門捕物帖睡前故事｜枕邊偵探社（無配樂版）"}},
    # Hornung's Raffles (†1921, 1899–1909) — public domain everywhere
    "洪農": {"label": "萊佛士", "who": "萊佛士", "first": 556, "gate": "RAFFLES-APPROVED.txt",
           "playlist": {"music": "萊佛士睡前故事｜枕邊偵探社", "nomusic": "萊佛士睡前故事｜枕邊偵探社（無配樂版）"}},
}
SEASONS["女偵探合輯"] = {"label": "女偵探", "who": "女偵探", "first": 706, "gate": "WOMEN-APPROVED.txt",   # , 5 books 1894–1915
                       "playlist": {"music": "女偵探睡前故事｜枕邊偵探社", "nomusic": "女偵探睡前故事｜枕邊偵探社（無配樂版）"}}
SEASONS["中國公案"] = {"label": "中國公案", "who": "中國公案", "first": 761, "gate": "GONGAN-APPROVED.txt",  # 狄公案／龍圖公案／鹿洲公案
                      "playlist": {"music": "中國公案睡前故事｜枕邊偵探社", "nomusic": "中國公案睡前故事｜枕邊偵探社（無配樂版）"}}
SEASONS["加博里歐"] = {"label": "勒寇克", "who": "勒寇克", "first": 861, "gate": "LECOQ-APPROVED.txt",   # Gaboriau †1873
                      "playlist": {"music": "勒寇克探長睡前故事｜枕邊偵探社", "nomusic": "勒寇克探長睡前故事｜枕邊偵探社（無配樂版）"}}
# Trent's Last Case (Bentley) + The Red House Mystery (Milne) — both authors †1956: UK public domain 2027-01-01
SEASONS["本特利"] = SEASONS["米恩"] = {"label": "黃金時代推理", "who": "黃金時代推理", "first": 591, "gate": "GOLDENAGE-APPROVED.txt",
                                  "not_before": (2027, 1, 1),
                                  "playlist": {"music": "黃金時代推理睡前故事｜枕邊偵探社",
                                               "nomusic": "黃金時代推理睡前故事｜枕邊偵探社（無配樂版）"}}
# the file that releases a season's production once the maintainer has picked its regulars' voices (rampo_queue.sh produce)
VOICES_OK = {103: "CHRISTIE", 171: "BROWN", 211: "LUPIN", 309: "HUOSANG", 386: "HANSHICHI", 436: "OLDMAN",
             486: "MOONSTONE", 506: "VANCE", 611: "UMON", 556: "RAFFLES", 591: "GOLDENAGE", 706: "WOMEN", 761: "GONGAN", 861: "LECOQ"}


def voices_ok(n, root):
    first = of_number(n)["first"]
    return first not in VOICES_OK or (root / f"{VOICES_OK[first]}-VOICES-OK").exists()


def of(cfg):
    return SEASONS.get(cfg.get("author"), SEASONS[None])


def of_number(n):
    """Season of a folder number (for code that only has the number)."""
    return max((s for s in SEASONS.values()), key=lambda s: s["first"] if s["first"] <= n else -1)
