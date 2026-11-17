"""The show's fixed ritual: every episode opens and closes the same way; only the story lines change.


"""

CHANNEL = "枕邊偵探社"


def night(cfg):
    """The night number shown to viewers . Episode folders keep the channel-wide number
 (Rampo = 79–102) so files never collide; the Rampo season is shown as its own 第1–24夜."""
    import season                                   # Christie = 103–170 → 阿嘉莎第1–68夜
    return cfg["number"] - season.of(cfg)["first"] + 1

NARRATOR = {
    "watson": "由我，華生，慢慢說給你聽。",
    "holmes": "這一次，說故事的是福爾摩斯自己。",
    "third": "我們慢慢說。",
    "friend": "由故事裡的那個「我」，慢慢說給你聽。",      # Rampo: the unnamed 私 of D坂, 二銭銅貨, 黒手組
    "hastings": "由白羅的老朋友海斯汀，慢慢說給你聽。",      # Christie
    "sheppard": "由村裡的謝潑德醫生，慢慢說給你聽。",
    "vicar": "由聖瑪麗米德村的牧師，慢慢說給你聽。",
    "baolang": "由霍桑的老朋友包朗，慢慢說給你聽。",      # 霍桑探案
}
CLOSING = {   # the default last image of each season
    "江戶川亂步睡前故事": "東京的夜深了，坂道上的燈一盞一盞熄了。<#1.0#>今晚，不會再有人來敲門了。",
    "阿嘉莎睡前故事": "英國鄉間的夜深了，壁爐裡的火慢慢暗了下來。<#1.0#>今晚，不會再有人來敲門了。",
    "亞森·羅蘋睡前故事": "巴黎的夜深了，塞納河上的燈光一盞一盞暗下來。<#1.0#>今晚，不會再有人來敲門了。",
    "霍桑探案睡前故事": "上海的夜深了，弄堂裡的燈一盞一盞熄了。<#1.0#>今晚，不會再有人來敲門了。",
    "半七捕物帳睡前故事": "江戶的夜深了，町裡的木戶一扇一扇關上，半七老人也把煙管收了起來。<#1.0#>今晚，不會再有人來敲門了。",
    "右門捕物帖睡前故事": "江戶的夜深了，八丁堀的燈一盞一盞熄了，沉默的右門也閉上了眼睛。<#1.0#>今晚，不會再有人來敲門了。",
    "萊佛士睡前故事": "倫敦的夜深了，奧爾巴尼公寓的燈熄了，萊佛士把最後一支菸捻熄。<#1.0#>今晚，不會再有人來敲門了。",
    "黃金時代推理睡前故事": "英國鄉間的夜深了，大宅裡的燈一盞一盞熄了，故事也在這裡停下。<#1.0#>今晚，不會再有人來敲門了。",
    "女偵探睡前故事": "夜深了，她把今晚的案子收進抽屜，熄了燈。<#1.0#>今晚，不會再有人來敲門了。",
    "中國公案睡前故事": "夜深了，衙門的大門關上了，堂上的燈也熄了。<#1.0#>今晚，不會再有人來擊鼓喊冤了。",
    "勒寇克探長睡前故事": "巴黎的夜深了，塞納河邊的煤氣燈一盞一盞熄了，勒寇克也收起了他的筆記。<#1.0#>今晚，不會再有人來敲門了。",
    "月光石睡前故事": "約克郡的夜深了，海邊的顫沙也安靜下來，月光石的故事，就停在這裡。<#1.0#>今晚，不會再有人來敲門了。",
    "菲洛·凡斯睡前故事": "紐約的夜深了，凡斯把最後一支菸捻熄，窗外的街燈一盞一盞暗了。<#1.0#>今晚，不會再有人來敲門了。",
    "角落裡的老人睡前故事": "倫敦的夜深了，ABC 茶館打烊了，角落那張大理石桌上，只留下一條打滿結的細繩。<#1.0#>今晚，不會再有人來敲門了。",
    "布朗神父睡前故事": "夜深了，布朗神父撐著他那把舊雨傘，慢慢走回小教堂。<#1.0#>今晚，不會再有人來敲門了。",   # stories go to America, Italy, France too
}


def intro(source_phrase, teaser, narrator="watson"):
    """source_phrase e.g. 「《福爾摩斯冒險史》裡的〈紅髮會〉」; teaser: one or two calm, spoiler-free sentences."""
    return (f"晚安，歡迎來到{CHANNEL}。<#1.0#>"
            "這裡是一間只在夜裡開門的偵探社。<#0.6#>"
            "案子會在故事的最後解開，你不用記住任何線索，安心聽就好。<#1.2#>"
            "請把燈調暗一點，讓自己舒服地躺好。<#1.2#>"
            f"今晚的故事，是{source_phrase}。<#0.8#>"
            f"{teaser}<#1.2#>"
            f"{NARRATOR[narrator]}")


def outro(closing=None, to_be_continued=False, series=None):
    """closing: optional story-specific image; defaults to the Baker Street fire."""
    if to_be_continued:
        return ("今晚就先說到這裡。<#1.2#>故事還沒結束，下一個夜晚，我們接著說。<#1.5#>"
                "晚安。<#0.8#>好好睡。")
    closing = closing or CLOSING.get(series) or "貝克街的爐火還亮著，福爾摩斯擱下了他的菸斗。<#1.0#>今晚，不會再有人來敲門了。"
    return f"故事就說到這裡了。<#1.2#>{closing}<#1.5#>晚安。<#0.8#>好好睡。"
