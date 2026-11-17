#!/usr/bin/env python3
"""Outline + translate + self-check one episode with MiniMax M3, paragraph-aligned.

Usage: translate.py <episode_dir>
Reads source/*.en.txt (Holmes) or source/*.ja.txt (Edogawa Rampo, season 2 — LANG["ja"]), episode.json
 script.json keeps the source text under "en" whatever its language, so review/speakers/fixkit need no change
Writes script/outline.json, script/script.json [{id, en, zh_raw, zh}], script/flags.json, script/script-zh.md
Updates episode.json: teaser, intro, outro, scenes (chapters; art is assigned by fetch_art.py), status=translated
Human review follows (review.py + apply_fixes.py) before narration.
"""
import glob, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import mm, show

SERIES_GLOSSARY = """\
Sherlock Holmes＝夏洛克·福爾摩斯（平常稱福爾摩斯）｜Dr. Watson／John H. Watson＝華生醫生／約翰·華生（平常稱華生）
Mrs. Hudson＝哈德森太太｜Mycroft Holmes＝麥考夫·福爾摩斯｜Lestrade＝雷斯垂德｜Gregson＝葛雷森｜Stanley Hopkins＝史丹利·霍普金斯
Professor Moriarty＝莫里亞蒂教授｜Colonel Sebastian Moran＝塞巴斯蒂安·莫蘭上校｜Irene Adler＝艾琳·艾德勒｜Billy（僮僕）＝比利
Mary Morstan＝瑪麗·摩斯坦｜Baker Street＝貝克街｜Scotland Yard＝蘇格蘭場｜the Strand＝河岸街｜Charing Cross＝查令十字
Waterloo＝滑鐵盧｜Paddington＝帕丁頓｜Victoria (station)＝維多利亞車站｜Surrey＝薩里郡｜Sussex＝薩塞克斯郡｜Kent＝肯特郡
Reichenbach＝萊辛巴赫｜sovereign（金幣）＝金鎊｜guinea＝基尼｜hansom＝雙輪小馬車"""

RULES = """1. 每一段都完整翻譯，不刪減情節，也不添加原著沒有的內容或比喻。
2. 輸出格式：每段開頭保留原本的編號標記（例如【P001】），一段一行，段與段之間空一行。編號的數量與順序必須和輸入完全一致。
3. 用台灣繁體中文和台灣慣用詞；全形標點。
4. 引號嚴格照英文的層次：英文 “ ” 一律用「」，英文 ‘ ’（引號裡的引號）才用『』；不要自己多包一層。英文段首有開引號、段尾沒有關引號（同一人連續好幾段的發言），中文也一樣段首「、段尾不關。
5. 稱呼語不是主詞。例如 “This gentleman, Mr. Wilson, has been my partner…” 是對威爾森說話，說的是「這位先生」。
6. 人稱（I／we／he／they）、時間（morning／afternoon／evening）、數量要跟原文完全一致；a couple of＝兩個左右。
7. 維多利亞時代的俚語、職業、器物要翻成實際意思，例如 smasher＝使假錢的人、I'll swing for it＝出了事我一個人擔、crib＝民宅。拿不準時保守翻出字面意思，不要猜。
8. 睡前朗讀語氣：平穩、溫和、口語自然。長句拆短，每句盡量不超過三十個字，用耳朵就聽得懂。
9. 不用驚嘆號，一律改成句號；問句保留問號。
10. 數字、年份、時間、金額一律寫成念出來的中文，例如「一八九〇年」「四英鎊」「十點鐘」「七號」。
11. 暴力或驚嚇的場面保留情節，但描寫放緩、不渲染。
12. 原著裡帶有種族、宗教、族群貶意的字眼，改成中性的描述，情節不變。
13. 外文引句（拉丁文、法文、德文）只翻中文意思。
14. 不要加譯註、標題、說明。
15. 專有名詞一律照對照表。"""

RAMPO_GLOSSARY = """\
明智小五郎＝明智小五郎（平常稱明智）｜Ｄ坂＝D坂｜白梅軒＝白梅軒｜小林少年＝小林少年｜波越警部＝波越警部
円＝圓｜銭＝錢｜巡査＝巡警｜刑事＝刑警｜警部＝警部｜判事＝法官｜予審判事＝預審法官｜下宿屋＝寄宿公寓｜書生＝寄宿的學生
女中＝女傭｜カフェ＝咖啡館｜古本屋＝舊書店｜蕎麦屋＝蕎麥麵店｜浴衣＝浴衣｜着物＝和服｜障子＝紙拉門｜襖＝隔扇｜大正＝大正"""

RAMPO_RULES = """1. 每一段都完整翻譯，不刪減情節，也不添加原著沒有的內容或比喻。
2. 輸出格式：每段開頭保留原本的編號標記（例如【P001】），一段一行，段與段之間空一行。編號的數量與順序必須和輸入完全一致。
3. 用台灣繁體中文和台灣慣用詞；全形標點。日文漢字一律改成台灣繁體字形（例：沢→澤、広→廣、団→團）。
4. 引號照原文：原文「」就用「」，『』就用『』；不要自己多包一層。原文段首有「、段尾沒有」（同一人連續好幾段的發言），中文也一樣。
5. 日本人名、地名保留漢字；平假名或片假名的名字依讀音配上合適的漢字或台灣慣用音譯，全篇一致。敬稱：「〜君」多半直接稱名（明智君→明智），「〜さん」依身分譯成先生、小姐、太太。
6. 人稱（私＝我）、時間、數量要跟原文完全一致。日文常省略主詞，中文要補上正確的主詞，不確定就照上下文最自然的讀法，不要改成別人。
7. 大正、昭和初年的器物、職業、制度翻成實際意思，例如下宿屋＝寄宿公寓、書生＝寄宿的學生、女中＝女傭、円本＝一圓一本的全集。拿不準時保守翻出字面意思，不要猜。
8. 睡前朗讀語氣：平穩、溫和、口語自然。長句拆短，每句盡量不超過三十個字，用耳朵就聽得懂。
9. 不用驚嘆號，一律改成句號；問句保留問號。
10. 數字、年份、時間、金額一律寫成念出來的中文，例如「大正十四年」「九月初」「五圓」「十點鐘」。
11. 暴力、屍體或驚嚇的場面保留情節，但描寫放緩、不渲染；情色的暗示只保留情節需要的最少部分。
12. 原著裡帶有身心障礙、種族、階級貶意的字眼，改成中性的描述，情節不變。
13. 外文或英文字母照原文（例如「D坂」），外文引句只翻中文意思。
14. 不要加譯註、標題、說明。
15. 專有名詞一律照對照表。"""

CHRISTIE_GLOSSARY = """\
Hercule Poirot＝赫丘勒·白羅（平常稱白羅）｜Captain Arthur Hastings＝亞瑟·海斯汀上尉（平常稱海斯汀）｜Inspector Japp＝傑普督察
Miss Jane Marple＝珍·瑪波小姐（平常稱瑪波小姐）｜Mr. Harley Quin＝哈利·奎因先生（平常稱奎因先生）｜Mr. Satterthwaite＝薩特斯韋特先生
Dr. Sheppard＝謝潑德醫生｜Caroline Sheppard＝卡洛琳·謝潑德｜Leonard Clement＝雷納德·克萊蒙（牧師）｜Griselda＝葛莉賽達
St. Mary Mead＝聖瑪麗米德村｜King's Abbot＝金艾博村｜Styles Court＝史岱爾莊｜Scotland Yard＝蘇格蘭場｜the Sûreté＝法國警察總署
mon ami＝我的朋友｜mon cher＝親愛的｜Mademoiselle＝小姐｜Madame＝夫人｜Monsieur＝先生｜little grey cells＝小小的灰色腦細胞"""

CHRISTIE_RULES = RULES.replace(
    "7. 維多利亞時代的俚語、職業、器物要翻成實際意思，例如 smasher＝使假錢的人、I'll swing for it＝出了事我一個人擔、crib＝民宅。拿不準時保守翻出字面意思，不要猜。",
    "7. 一九二〇年代英國的俚語、職業、器物要翻成實際意思，例如 bridge＝橋牌、the Yard＝蘇格蘭場、two-seater＝雙人座小汽車、"
    "char/charwoman＝打掃的女工。拿不準時保守翻出字面意思，不要猜。").replace(
    "13. 外文引句（拉丁文、法文、德文）只翻中文意思。",
    "13. 白羅常夾雜法文（mon ami、Mon Dieu、Voilà、précisément 等），一律只翻中文意思，語氣保留他客氣又略帶自負的說話方式；"
    "他把英文說得不太道地的地方，翻成通順中文即可，不要故意寫錯。")
assert CHRISTIE_RULES != RULES

BROWN_GLOSSARY = """\
Father Brown＝布朗神父｜Flambeau＝弗朗博｜Aristide Valentin＝亞里斯提德·瓦朗坦｜Scotland Yard＝蘇格蘭場
Mass＝彌撒｜priest＝神父｜curate＝助理牧師｜vicar＝教區牧師｜Essex＝艾塞克斯郡｜Cobhole＝科布霍爾"""

BROWN_RULES = CHRISTIE_RULES.replace("一九二〇年代英國", "一九一〇到二〇年代英國").replace(
    "13. 白羅常夾雜法文（mon ami、Mon Dieu、Voilà、précisément 等），一律只翻中文意思，語氣保留他客氣又略帶自負的說話方式；"
    "他把英文說得不太道地的地方，翻成通順中文即可，不要故意寫錯。",
    "13. 外文引句（拉丁文、法文、義大利文）只翻中文意思。卻斯特頓愛用悖論和長句，意思要完整，但拆成短句、用耳朵聽得懂。"
    "宗教用語照台灣天主教慣用（神父、彌撒、告解、修士）。")
assert BROWN_RULES != CHRISTIE_RULES

# season: Baroness Orczy, The Old Man in the Corner (Edwardian London)
OLDMAN_GLOSSARY = """\
the old man in the corner＝角落裡的老人（全季固定稱呼，不給本名）｜Polly Burton＝寶莉·伯頓｜Richard Frobisher＝理查·弗羅比舍
Evening Observer＝《晚間觀察家報》｜London Mail＝《倫敦郵報》｜A.B.C. shop＝ABC 茶館（諾福克街分店）
Scotland Yard＝蘇格蘭場｜inquest＝死因審訊｜coroner＝驗屍官｜magistrate＝治安法官｜Old Bailey＝老貝利法院"""

OLDMAN_RULES = BROWN_RULES.replace("一九一〇到二〇年代英國", "一九〇〇到二〇年代英國").replace(
    "卻斯特頓愛用悖論和長句，意思要完整，但拆成短句、用耳朵聽得懂。宗教用語照台灣天主教慣用（神父、彌撒、告解、修士）。",
    "老人說話又快又得意，常用反問句和「你看」「你懂嗎」，譯文保留這種碎念的口氣；他講案情時的長段落要拆成好聽的短句。"
    "手裡那條細繩和打結的動作照實譯出；他喝的是一杯牛奶。")
assert OLDMAN_RULES != BROWN_RULES

# season: Wilkie Collins, The Moonstone (Yorkshire and London, 1848–49; several first-person narrators)
MOONSTONE_GLOSSARY = """\
the Moonstone＝月光石｜Gabriel Betteredge＝加百列·貝特瑞吉｜Lady Julia Verinder＝茱莉亞·維林德夫人｜Rachel Verinder＝瑞秋·維林德
Franklin Blake＝富蘭克林·布萊克｜Godfrey Ablewhite＝戈弗雷·艾布爾懷特｜Drusilla Clack＝德魯西拉·克拉克（克拉克小姐）
Mathew Bruff＝馬修·布魯夫｜Ezra Jennings＝以斯拉·詹寧斯｜Mr. Candy＝坎迪醫生｜Sergeant Cuff＝卡夫警長
Superintendent Seegrave＝西格雷夫督察｜Rosanna Spearman＝蘿莎娜·斯皮爾曼｜Penelope＝潘妮洛普｜John Herncastle＝約翰·赫恩卡索
Mr. Murthwaite＝默思韋特先生｜Septimus Luker＝塞普蒂默斯·盧克｜Limping Lucy＝跛腳露西｜Gooseberry＝鵝莓（男孩）
the Shivering Sand＝顫沙｜Frizinghall＝弗里辛霍爾｜Seringapatam＝塞林伽巴丹｜the Indians／Brahmins／jugglers＝三名印度人／婆羅門
Robinson Crusoe＝《魯賓遜漂流記》"""

MOONSTONE_RULES = RULES.replace("13. 外文引句（拉丁文、法文、德文）只翻中文意思。",
    "13. 外文引句（拉丁文、法文、德文）只翻中文意思。這本書由好幾位敘事者輪流寫，每一段的「我」是誰照原文，口氣要分得出來："
    "老管家貝特瑞吉囉嗦、愛引《魯賓遜漂流記》；克拉克小姐偽善做作（保留可笑，不要翻成說教）；律師布魯夫簡潔。"
    "對印度人的輕蔑字眼（Hindoo、heathen、natives）一律中性化，情節不變。")
assert MOONSTONE_RULES != RULES

# season: S. S. Van Dine, Philo Vance (New York, 1926–1930; narrated by Van Dine, Vance's lawyer friend)
VANCE_GLOSSARY = """\
Philo Vance＝菲洛·凡斯｜John F.-X. Markham＝約翰·馬克漢（地方檢察官）｜Sergeant Ernest Heath＝希茲警官｜Van Dine＝范·達因（旁白「我」）
Currie＝柯里（凡斯的管家）｜Swacker＝斯瓦克（檢察官祕書）｜Dr. Emanuel Doremus＝多雷默斯醫生（法醫）｜Captain Hagedorn＝哈格多恩隊長
Captain Dubois＝杜布瓦隊長｜Inspector Moran＝莫蘭督察｜District Attorney＝地方檢察官｜Homicide Bureau＝重案組
the Stuyvesant Club＝斯圖文森俱樂部｜Criminal Courts Building＝刑事法院大樓"""

VANCE_RULES = CHRISTIE_RULES.replace("一九二〇年代英國", "一九二〇年代紐約").replace(
    "13. 白羅常夾雜法文（mon ami、Mon Dieu、Voilà、précisément 等），一律只翻中文意思，語氣保留他客氣又略帶自負的說話方式；"
    "他把英文說得不太道地的地方，翻成通順中文即可，不要故意寫錯。",
    "13. 凡斯說話矯飾又慵懶（Y' know、my dear fellow、deuced、吞音），翻成輕、慢、帶點揶揄的書面口語，不要翻成市井口語；"
    "他夾雜的法文、拉丁文、德文只翻中文意思。他談藝術、心理學的長篇大論照翻（意思完整、拆成短句），不可自行刪節。"
    "時代用語（wop、mulatto 等）一律中性化，情節不變。")
assert VANCE_RULES != CHRISTIE_RULES

# season: 岡本綺堂《半七捕物帳》(Edo told in the Meiji years by old Hanshichi to the young 「我」)
HANSHICHI_GLOSSARY = """\
半七＝半七（「半七老人」「半七先生」；不意譯）｜捕物帳＝捕物帳｜岡っ引＝岡引（第一次出現補一句：協助官差的民間捕快）｜目明し＝目明
同心＝同心｜与力＝與力｜奉行所＝奉行所｜親分＝親分｜旦那＝旦那｜十手＝十手｜子分＝手下｜自身番＝自身番（町內的崗哨）
長屋＝長屋（大雜院）｜両＝兩｜分＝分｜朱＝朱｜文＝文（貨幣照寫不換算）｜文久二年＝文久二年（1862，第一次出現加西曆）
神田｜三河町｜赤坂｜日本橋｜淺草｜向島｜兩國｜本所｜深川｜牛込｜小石川｜番町｜芝｜麻布｜品川｜內藤新宿｜隅田川｜神田川
わたし＝我（明治年間拜訪半七老人的年輕報社記者）｜敬稱用親分、旦那、先生，不加「大人」"""

HANSHICHI_RULES = RAMPO_RULES.replace(
    "7. 大正、昭和初年的器物、職業、制度翻成實際意思，例如下宿屋＝寄宿公寓、書生＝寄宿的學生、女中＝女傭、円本＝一圓一本的全集。拿不準時保守翻出字面意思，不要猜。",
    "7. 江戶時代的器物、職業、制度翻成實際意思，第一次出現時用短短幾個字說明（例如岡っ引＝岡引、自身番＝町內的崗哨、駕籠＝轎子、"
    "辻番＝路口的守衛）；時辰只在需要時換算，否則保留「五更」之類的氛圍。故事是兩層：「我」問、老人講，老人講述放在「」裡，裡面再引別人的話用『』。半七老人說話是明治年間老江戶人的口吻，"
    "親切、慢條斯理，愛說「那時候啊」；譯文保留這種說故事的口氣。拿不準時保守翻出字面意思，不要猜。")
assert HANSHICHI_RULES != RAMPO_RULES

# season: 佐々木味津三《右門捕物帖》(Edo, 1630s–40s; a storyteller's voice, no 「我」)
UMON_GLOSSARY = """\
むっつり右門＝沉默的右門（第一次出現補一句：大家都叫他沉默的右門）｜近藤右門＝近藤右門｜名人＝名人｜おしゃべり伝六＝話多的傳六
あばたの敬四郎＝麻臉的敬四郎（第一次說「臉上有麻子的敬四郎」，之後只叫敬四郎）｜松平伊豆守信綱＝松平伊豆守信綱｜家光＝將軍家光
善光寺辰＝善光寺辰｜お静＝阿靜｜くし巻きお由＝髻捲阿由｜同心＝同心｜岡っ引＝岡引｜奉行所＝奉行所｜八丁堀＝八丁堀
旦那（傳六叫右門）＝大爺｜てがら＝功勞（「第三番てがら」＝這是右門的第三件功勞）｜寛永十五年＝寬永十五年（1638，第一次加西曆）
草香流柔術＝草香流柔術｜逆腕＝反擰手臂"""

UMON_RULES = HANSHICHI_RULES.replace(
    "半七老人說話是明治年間老江戶人的口吻，親切、慢條斯理，愛說「那時候啊」；譯文保留這種說故事的口氣。",
    "原文是講談說書人的口吻（…でございます），譯成平靜、節奏慢的台灣口語，保留說書人偶爾的調侃；傳六話多又急，"
    "口頭禪譯成「哎呀」「我說啊」，不用粗話；右門話少，一開口就是重點。歧視字眼（気違い、めくら、かたわ、非人、乞食）"
    "一律換中性說法；人頭、血跡、拷問的描寫放緩淡化，情節不刪。").replace(
    "故事是兩層：「我」問、老人講，老人講述放在「」裡，裡面再引別人的話用『』。", "")
assert UMON_RULES != HANSHICHI_RULES

# seasons: Hornung's Raffles (London, 1890s; Bunny tells it as 「我」) and the golden-age pair (England, 1910s–20s)
RAFFLES_GLOSSARY = """\
A. J. Raffles＝萊佛士｜Bunny Manders＝邦尼·曼德斯（第一次出現：哈利·「邦尼」·曼德斯，之後只叫邦尼）
Inspector Mackenzie＝麥肯齊督察｜Crawshay＝克勞肖｜the Albany＝奧爾巴尼公寓｜Piccadilly＝皮卡迪利｜Scotland Yard＝蘇格蘭場
Lord's＝羅德板球場｜Gentlemen v Players＝紳士隊對職業隊｜Test Match＝國際對抗賽｜century＝一百分｜wicket＝三柱門"""

RAFFLES_RULES = RULES.replace("13. 外文引句（拉丁文、法文、德文）只翻中文意思。",
    "13. 外文引句（拉丁文、法文、德文）只翻中文意思。萊佛士瀟灑、愛開玩笑，邦尼（敘事的「我」）崇拜他又常提心吊膽，"
    "口氣要分得出來；板球術語第一次出現給一句白話。種族或族裔稱呼（例如放貸人被叫「猶太人」「夏洛克」）一律拿掉，情節不變。")
assert RAFFLES_RULES != RULES

GOLDENAGE_GLOSSARY = """\
Philip Trent＝菲利普·特倫特｜Sigsbee Manderson＝席格斯比·曼德森｜Mabel Manderson＝瑪貝爾·曼德森｜Mr. Cupples＝庫普斯先生
John Marlowe＝約翰·馬洛｜Calvin Bunner＝卡爾文·邦納｜Inspector Murch＝默奇督察｜Sir James Molloy＝詹姆斯·莫洛伊爵士｜Martin＝馬丁
Antony Gillingham＝安東尼·吉林漢（朋友叫他東尼）｜Bill Beverley＝比爾·貝佛利｜Red House＝紅屋｜Mark Ablett＝馬克·阿布利特
Robert Ablett＝羅伯特·阿布利特｜Matthew Cayley＝馬修·凱利｜Audrey Stevens＝奧黛麗·史蒂文斯｜Inspector Birch＝伯奇督察
Betty Calladine＝貝蒂·卡拉丁｜Watson＝華生"""

GOLDENAGE_RULES = CHRISTIE_RULES.replace("一九二〇年代英國", "一九一〇到二〇年代英國").replace(
    "13. 白羅常夾雜法文（mon ami、Mon Dieu、Voilà、précisément 等），一律只翻中文意思，語氣保留他客氣又略帶自負的說話方式；"
    "他把英文說得不太道地的地方，翻成通順中文即可，不要故意寫錯。",
    "13. 偵探推理講解的長段落意思一個都不能漏，不可壓縮邏輯，但拆成短句；吉林漢和比爾之間的玩笑（包括「華生」梗）保留輕快口氣。"
    "舊式種族字眼一律中性化，情節不變。")
assert GOLDENAGE_RULES != CHRISTIE_RULES

# season: Chinese 公案 classics (狄公案原典、龍圖公案、鹿洲公案) — classical / early-vernacular Chinese rewritten
# as modern spoken Taiwanese Mandarin for listening; same machinery as a translation ("翻" = 改寫成白話)
GONGAN_GLOSSARY = """\
狄仁傑＝狄仁傑（狄公）｜包拯＝包拯（包公）｜藍鼎元＝藍鼎元｜縣令＝縣令｜知縣＝知縣｜知府＝知府｜府尹＝府尹｜衙役＝衙役
捕快＝捕快｜仵作＝仵作（驗屍的官差，第一次出現補一句）｜公堂＝公堂｜升堂＝升堂｜師爺＝師爺｜銀＝兩銀子"""

GONGAN_RULES = """1. 這是改寫，不是摘要：每一段的情節、人物、對白、線索都要完整保留，不刪減、不添加原著沒有的情節或比喻。
2. 輸出格式：每段開頭保留原本的編號標記（例如【P001】），一段一行，段與段之間空一行。編號的數量與順序必須和輸入完全一致。
3. 把文言和古白話改寫成現代台灣口語，讓人「用耳朵聽得懂」：句子短、主詞清楚、用今天的說法（「曰」＝說、「吾」＝我、「汝」＝你）。
   保留一點古代說書的味道，但不要文謅謅；台灣繁體字、全形標點。
4. 對白一律放進「」，引號裡再引別人的話用『』；誰說的照原文，原文省略主詞時補上正確的人。
5. 官職、制度、器物第一次出現時用幾個字說明（例如仵作＝負責驗屍的官差、升堂＝開庭審案），之後直接用。人名、地名保留原字。
6. 章回小說的套語（「話說」「卻說」「且聽下回分解」「有詩為證」）：開頭的可以留一句當說書口氣，回末的「且聽下回分解」和詩詞贊語刪掉，
   夾在故事中的詩詞只在跟情節有關時改寫成一兩句白話。
7. 刑求、酷刑、屍體、鬼魂的描寫放緩淡化，情節照留；歧視字眼一律中性化。帶性暗示或極殘酷的刑罰場面（例如木驢遊街）
   整段只留一句結果（例如「後來依律處決」），不描寫過程。
8. 數字、時間、地名、親屬關係要跟原文完全一致。"""

# season: women detectives 1894–1915 (Loveday Brooke, Dorcas Dene, Hilda Wade, Lady Molly, Violet Strange)
WOMEN_GLOSSARY = """\
Loveday Brooke＝洛芙黛·布魯克（之後稱洛芙黛或布魯克小姐）｜Ebenezer Dyer＝艾比尼澤·戴爾｜Lynch Court＝林奇院
Lady Molly Robertson-Kirk＝茉莉夫人｜Mary Granard＝瑪麗·格蘭納德（敘事的「我」）｜Violet Strange＝薇奧莉·斯特蘭奇（稱薇奧莉）
Dorcas Dene＝多卡絲·丁恩｜Saxon Trent＝薩克森·特倫特（敘事的「我」）｜Hilda Wade＝希爾達·韋德｜Professor Sebastian＝塞巴斯蒂安教授
Dr. Cumberledge＝卡伯蘭奇醫生（敘事的「我」）｜St. Nathaniel's Hospital＝聖納撒尼爾醫院｜Scotland Yard＝蘇格蘭場"""

WOMEN_RULES = CHRISTIE_RULES.replace("一九二〇年代英國", "一八九〇到一九一〇年代的英國與美國").replace(
    "13. 白羅常夾雜法文（mon ami、Mon Dieu、Voilà、précisément 等），一律只翻中文意思，語氣保留他客氣又略帶自負的說話方式；"
    "他把英文說得不太道地的地方，翻成通順中文即可，不要故意寫錯。",
    "13. 五位女偵探各有各的做事方式，不要互相套用「福爾摩斯式」比喻。殖民地與種族用語（Kaffir、Hottentot、half-caste、"
    "savages、gipsy 等）一律中性化（當地人、非洲僕工、馬塔貝列人、混血、羅姆人），情節與立場不改；字母密碼不要照念字母，"
    "改成用中文描述「一串字母」。")
assert WOMEN_RULES != CHRISTIE_RULES

FR_GLOSSARY = """\
Arsène Lupin＝亞森·羅蘋（平常稱羅蘋）｜Ganimard＝加尼瑪爾（探長）｜Herlock Sholmès＝赫洛克·夏爾摩斯（平常稱夏爾摩斯）
Wilson＝威爾森｜Isidore Beautrelet＝伊吉多·波特萊｜prince Paul Sernine＝保羅·塞寧親王｜M. Lenormand＝勒諾曼先生
Daubrecq＝多布雷克｜don Luis Perenna＝唐·路易·佩雷納｜prince Rénine＝雷寧親王｜Hortense Daniel＝奧坦絲·丹尼爾
Jim Barnett＝吉姆·巴奈特｜Béchoux＝貝舒｜Joséphine Balsamo＝約瑟芬·巴爾薩摩｜Raoul d’Andrésy＝拉烏爾·丹德雷齊
Raoul de Limézy＝拉烏爾·德·利梅齊｜Jean d’Enneris＝尚·丹內里斯｜Victoire＝維克托娃｜Grognard＝格羅尼亞
la Sûreté＝保安局｜le juge d’instruction＝預審法官｜le préfet de police＝警察總監｜commissaire＝警長
M.＝先生｜Mme＝夫人｜Mlle＝小姐｜Étretat＝埃特爾塔｜Paris＝巴黎｜la Seine＝塞納河"""

FR_RULES = RULES.replace(
    "4. 引號嚴格照英文的層次：英文 “ ” 一律用「」，英文 ‘ ’（引號裡的引號）才用『』；不要自己多包一層。英文段首有開引號、段尾沒有關引號（同一人連續好幾段的發言），中文也一樣段首「、段尾不關。",
    "4. 法文對白的格式要改成中文引號：以「— 」（破折號）開頭的對白段落，把說的話放進「」裡，旁白插句（dit-il、s’écria Lupin）放在引號外；"
    "同一段裡破折號又換人說話時，各自一組「」。« » 一律用「」，引號裡的引號用『』。« 開頭、段尾沒有 »（同一人連續好幾段），中文也段首「、段尾不關。").replace(
    "7. 維多利亞時代的俚語、職業、器物要翻成實際意思，例如 smasher＝使假錢的人、I'll swing for it＝出了事我一個人擔、crib＝民宅。拿不準時保守翻出字面意思，不要猜。",
    "7. 二十世紀初法國的職業、制度、器物要翻成實際意思，例如 juge d’instruction＝預審法官、la Sûreté＝保安局、concierge＝門房、"
    "fiacre＝出租馬車、apache＝巴黎的流氓。拿不準時保守翻出字面意思，不要猜。").replace(
    "13. 外文引句（拉丁文、法文、德文）只翻中文意思。",
    "13. 原文夾雜的英文、拉丁文、義大利文只翻中文意思，不留外文。法文的雙關、字謎若是解謎關鍵，保留解謎邏輯，用中文說清楚意思。")
assert FR_RULES.count("法文對白") == 1 and "二十世紀初法國" in FR_RULES

# season: Émile Gaboriau, Monsieur Lecoq (Paris and the provinces, 1815–1860s; translated from French)
LECOQ_GLOSSARY = """\
Lecoq＝勒寇克（勒寇克先生）｜le père Tabaret＝塔巴雷老爹｜Tirauclair＝提羅克萊（人稱「明察」）｜Gévrol＝熱弗羅｜le père Absinthe＝苦艾老爹
Fanferlot＝方費洛（綽號「松鼠」）｜juge d’instruction＝預審法官｜juge de paix＝治安法官｜commissaire＝警長｜la Sûreté＝保安處
Préfecture de police＝警察廳｜Daburon＝達布隆｜Noël Gerdy＝諾埃爾·熱迪｜veuve Lerouge＝勒魯菊寡婦｜La Jonchère＝拉容榭｜Bougival＝布吉瓦
Commarin＝科馬蘭｜père Plantat＝普朗塔老爹｜Hector de Trémorel＝埃克托·德·特雷莫雷爾｜Sauvresy＝索夫雷西｜Berthe＝貝爾特｜Orcival＝奧爾西瓦
Valfeuillu＝瓦爾弗伊莊園｜docteur Gendron＝讓德宏醫生｜André Fauvel＝安德烈·福維爾｜Prosper Bertomy＝普羅斯佩·貝爾托米｜Madeleine＝瑪德蓮
Raoul de Lagors＝拉烏爾·德·拉戈爾｜Louis de Clameran＝路易·德·克拉梅朗｜Nina Gypsy＝妮娜·吉普賽｜Verduret＝維迪雷先生
Mai＝梅｜la Poivrière＝胡椒罐酒館｜la veuve Chupin＝舒潘寡婦｜Segmuller＝賽格米勒｜duc de Sairmeuse＝賽爾默茲公爵｜Martial＝馬夏爾
Lacheneur＝拉謝納｜Marie-Anne＝瑪麗—安｜Blanche de Courtomieu＝布朗希·德·庫爾托米厄｜Escorval＝埃斯科瓦爾｜abbé Midon＝米東神父
de＝德｜M.＝先生｜Mme＝夫人｜Mlle＝小姐｜père／mère（老人）＝老爹／大媽"""

LECOQ_RULES = FR_RULES.replace("二十世紀初法國", "十九世紀法國（復辟時期到第二帝國）").replace(
    "13. 原文夾雜的英文、拉丁文、義大利文只翻中文意思，不留外文。",
    "13. 原文夾雜的英文、拉丁文、義大利文只翻中文意思，不留外文。後半的長篇前史照翻，不要摘要；下毒的毒物名稱與劑量、"
    "屍體與驗屍、鎮壓與處決的細節概括成一兩句（例如「他一天比一天虛弱」），情節不變。「梅」的真名在揭曉前不能提前透露。")
assert LECOQ_RULES != FR_RULES


LANG = {                                    # everything that differs between the Holmes and the Rampo seasons
    "en": {"name": "英文", "tag": "EN", "rules": RULES, "glossary": SERIES_GLOSSARY, "author": "柯南·道爾的福爾摩斯故事（英文原著，公版）",
           "editor": "福爾摩斯故事的有聲書編輯", "gloss_key": "英文專有名詞", "size": lambda p: len(p.split()), "chunk": 1500,
           "slang": "俚語誤解"},
    "ja": {"name": "日文", "tag": "JA", "rules": RAMPO_RULES, "glossary": RAMPO_GLOSSARY, "author": "江戶川亂步的偵探小說（日文原著，公版）",
           "editor": "江戶川亂步偵探小說的有聲書編輯", "gloss_key": "日文專有名詞", "size": len, "chunk": 3500,
           "slang": "日文省略主詞時補錯人"},
    "christie": {"name": "英文", "tag": "EN", "rules": CHRISTIE_RULES, "glossary": CHRISTIE_GLOSSARY,      # season 3
                 "author": "阿嘉莎·克莉絲蒂的推理小說（英文原著，在台灣與美國已屬公版）",
                 "editor": "阿嘉莎·克莉絲蒂推理小說的有聲書編輯", "gloss_key": "英文專有名詞",
                 "size": lambda p: len(p.split()), "chunk": 1500, "slang": "俚語誤解"},
    "fr": {"name": "法文", "tag": "FR", "rules": FR_RULES, "glossary": FR_GLOSSARY,      # season 5 (Lupin)
           "author": "莫里斯·盧布朗的亞森·羅蘋探案（法文原著，公版）", "editor": "亞森·羅蘋探案的有聲書編輯",
           "gloss_key": "法文專有名詞", "size": lambda p: len(p.split()), "chunk": 1500, "slang": "法文慣用語直譯"},
    "brown": {"name": "英文", "tag": "EN", "rules": BROWN_RULES, "glossary": BROWN_GLOSSARY,      # season 4
              "author": "卻斯特頓的布朗神父探案（英文原著，公版）", "editor": "布朗神父探案的有聲書編輯",
              "gloss_key": "英文專有名詞", "size": lambda p: len(p.split()), "chunk": 1500, "slang": "俚語誤解"},
    "oldman": {"name": "英文", "tag": "EN", "rules": OLDMAN_RULES, "glossary": OLDMAN_GLOSSARY,      #
               "author": "奧希茲的〈角落裡的老人〉探案（英文原著，公版）", "editor": "角落裡的老人探案的有聲書編輯",
               "gloss_key": "英文專有名詞", "size": lambda p: len(p.split()), "chunk": 1500, "slang": "俚語誤解"},
    "moonstone": {"name": "英文", "tag": "EN", "rules": MOONSTONE_RULES, "glossary": MOONSTONE_GLOSSARY,      #
                  "author": "威爾基·柯林斯的《月光石》（英文原著，公版）", "editor": "《月光石》的有聲書編輯",
                  "gloss_key": "英文專有名詞", "size": lambda p: len(p.split()), "chunk": 1500, "slang": "俚語誤解"},
    "vance": {"name": "英文", "tag": "EN", "rules": VANCE_RULES, "glossary": VANCE_GLOSSARY,      #
              "author": "范·達因的菲洛·凡斯探案（英文原著，公版）", "editor": "菲洛·凡斯探案的有聲書編輯",
              "gloss_key": "英文專有名詞", "size": lambda p: len(p.split()), "chunk": 1500, "slang": "俚語誤解"},
    "hanshichi": {"name": "日文", "tag": "JA", "rules": HANSHICHI_RULES, "glossary": HANSHICHI_GLOSSARY,      #
                  "author": "岡本綺堂的《半七捕物帳》（日文原著，公版）", "editor": "《半七捕物帳》的有聲書編輯",
                  "gloss_key": "日文專有名詞", "size": len, "chunk": 3500, "slang": "日文省略主詞時補錯人"},
    "umon": {"name": "日文", "tag": "JA", "rules": UMON_RULES, "glossary": UMON_GLOSSARY,      #
             "author": "佐佐木味津三的《右門捕物帖》（日文原著，公版）", "editor": "《右門捕物帖》的有聲書編輯",
             "gloss_key": "日文專有名詞", "size": len, "chunk": 3500, "slang": "日文省略主詞時補錯人"},
    "raffles": {"name": "英文", "tag": "EN", "rules": RAFFLES_RULES, "glossary": RAFFLES_GLOSSARY,      #
                "author": "洪農的紳士怪盜萊佛士（英文原著，公版）", "editor": "萊佛士故事的有聲書編輯",
                "gloss_key": "英文專有名詞", "size": lambda p: len(p.split()), "chunk": 1500, "slang": "俚語誤解"},
    "goldenage": {"name": "英文", "tag": "EN", "rules": GOLDENAGE_RULES, "glossary": GOLDENAGE_GLOSSARY,      #
                  "author": "本特利與米恩的黃金時代推理小說（英文原著，在台灣與美國已屬公版）", "editor": "黃金時代推理小說的有聲書編輯",
                  "gloss_key": "英文專有名詞", "size": lambda p: len(p.split()), "chunk": 1500, "slang": "俚語誤解"},
    "lecoq": {"name": "法文", "tag": "FR", "rules": LECOQ_RULES, "glossary": LECOQ_GLOSSARY,      #
              "author": "加博里歐的勒寇克探案（法文原著，公版）", "editor": "勒寇克探案的有聲書編輯",
              "gloss_key": "法文專有名詞", "size": lambda p: len(p.split()), "chunk": 1500, "slang": "法文慣用語直譯"},
    "gongan": {"name": "古典中文", "tag": "WY", "rules": GONGAN_RULES, "glossary": GONGAN_GLOSSARY,      #
               "author": "中國古典公案小說（文言與古白話，公版）", "editor": "中國公案故事的有聲書改編編輯",
               "gloss_key": "原文人名官名", "size": len, "chunk": 3000, "slang": "文言誤讀"},
    "women": {"name": "英文", "tag": "EN", "rules": WOMEN_RULES, "glossary": WOMEN_GLOSSARY,      #
              "author": "維多利亞到愛德華時代的女偵探小說（英文原著，公版）", "editor": "女偵探故事的有聲書編輯",
              "gloss_key": "英文專有名詞", "size": lambda p: len(p.split()), "chunk": 1500, "slang": "俚語誤解"},
    # season 6 (霍桑探案): Chinese original — nothing is translated; only the outline (teaser, scenes) is asked for
    "zh": {"name": "中文", "tag": "ZH", "rules": "", "glossary": "（無）", "author": "程小青的霍桑探案（中文原著）",
           "editor": "霍桑探案的有聲書編輯", "gloss_key": "中文人名地名", "size": len, "chunk": 3500, "slang": ""},
}


def to_traditional(paras):
    """霍桑探案: the source is the Chinese original. Simplified text goes through OpenCC s2tw (characters and
 Taiwan variants only — never s2twp, whose phrase table would rewrite a 1920s author's words); text that is
 already Traditional is left alone."""
    import subprocess
    text = "\n\n".join(paras)
    conv = subprocess.run(["opencc", "-c", "s2tw"], input=text, capture_output=True, text=True, check=True).stdout
    changed = sum(a != b for a, b in zip(text, conv))
    if changed < len(re.findall(r"[㐀-鿿]", text)) * 0.02:       # already Traditional: under 2 % would change
        return paras
    for a, b in ZH_FIX:
        conv = re.sub(a, b, conv)
    out = conv.split("\n\n")
    assert len(out) == len(paras), (len(out), len(paras))
    return out


# s2tw is character-by-character; these are the wrong picks found over all 24 霍桑 stories (surnames 余/范,
# 幹 "do", aspect 了 after 查明…). The reviewers check the rest (HUOSANG-REVIEW-BRIEF.md).
ZH_FIX = [
    (r"餘(?=甘棠|少爺|先生|小姐|太太|家)", "余"), (r"姓餘", "姓余"), (r"芝範", "芝范"), (r"瓷鍾", "瓷鐘"),
    (r"(?<=[他她伊誰人己們客著])乾(?=的)", "幹"), (r"乾(?=什麼|麼|嗎)", "幹"),
    (r"(?<=[查探問瞧記說證聲指訪弄打天])明瞭", "明了"), (r"年曆史", "年歷史"),
    (r"(?<=[這那])週(?=[媽碼番])", "周"),
    # 代決 (聽得懂優先): 1920s 「伊」＝她 (2,387 times — read yī it sounds like 一), sentence-final 「罷」＝吧
    (r"(?<!木乃)伊(?![斯甸麗利犁朗拉])", "她"), (r"(?<![說言作])罷(?=[。？！」”])", "吧"),
]


def lang(cfg):
    return LANG[cfg.get("lang_profile", cfg.get("source_lang", "en"))]


MARK = re.compile(r"【P(\d{3})】\s*(.*?)(?=\s*【P\d{3}】|\Z)", re.S)


def numbered(paras, idxs):
    return "\n\n".join(f"【P{i + 1:03d}】{paras[i]}" for i in idxs)


def chunks(paras, max_words=1500, size=lambda p: len(p.split())):
    out, cur, n = [], [], 0
    for i, p in enumerate(paras):
        w = size(p)
        if cur and n + w > max_words:
            out.append(cur); cur, n = [], 0
        cur.append(i); n += w
    if cur:
        out.append(cur)
    return out


def json_block(text):
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    body = m.group(1) if m else text
    start = min([i for i in (body.find("{"), body.find("[")) if i >= 0])
    return json.loads(body[start:body.rfind("}" if body[start] == "{" else "]") + 1])


def blocked(e):
    """MiniMax's input filter (HTTP 500 "new_sensitive (1026)")."""
    return "1026" in str(e) or "sensitive" in str(e)


def outline(cfg, paras):
    """episodes 83/87 (Rampo): the whole story in one request trips the input filter. Fall back to the first 80
 characters of each paragraph (enough to cut scenes and list names), then to the check model."""
    try:
        return _outline(cfg, paras)
    except RuntimeError as e:
        if not blocked(e):
            raise
        print("  outline blocked by the content filter: retrying on paragraph heads", flush=True)
    heads = [p[:80] for p in paras]
    try:
        return _outline(cfg, heads)
    except RuntimeError as e:
        if not blocked(e):
            raise
        print("  outline still blocked: retrying with the check model", flush=True)
    return _outline(cfg, heads, model=mm.CHECK_MODEL)


def _outline(cfg, paras, model=None):
    L = lang(cfg)
    system = f"你是{L['editor']}，替台灣大人的睡前故事頻道做準備工作。只輸出 JSON。"
    user = f"""下面是〈{cfg['title']}〉（{cfg['title_en']}）的{L['name']}原著，已經逐段編號。請輸出一個 JSON 物件：
{{
 "teaser": "一到兩句、不劇透、語氣平靜的故事引子（台灣繁體，不超過四十字，不要提到結局或兇手）",
 "glossary": [{{"en": "{L['gloss_key']}", "zh": "台灣繁體譯名"}}],
 "scenes": [{{"start": "P001", "chapter": "四到八個字的章節名"}}],
 "sensitive": ["需要放緩或改成中性描述的段落編號"]
}}
規則：glossary 列出故事裡所有人名、地名、船名、機構名（下面系列對照表已有的照用，不必重列）；scenes 切成六到十二段，在時間或地點轉換處切，第一段必須從 P001 開始，編號要遞增。

系列對照表：
{L['glossary']}

原文：
{numbered(paras, range(len(paras)))}"""
    for attempt in range(3):
        text, usage, stop = mm.m3(system, user, max_tokens=32000, model=model,
                                  effort="medium")   # M3.1 Flash spent all 8000 on thinking
        try:
            o = json_block(text)
            ids = [s["start"] for s in o["scenes"]]
            assert ids and ids[0] == "P001" and ids == sorted(set(ids)), ids
            assert all(re.fullmatch(r"P\d{3}", i) and int(i[1:]) <= len(paras) for i in ids), ids
            return o, usage
        except Exception as e:
            print(f"  outline attempt {attempt + 1} invalid: {e}", flush=True)
    raise SystemExit("outline failed")


def translate_chunk(k, total, idxs, paras, cfg, glossary, model=None):
    """ a chunk the input filter refuses is halved until the refused paragraph stands alone; a lone refused
 paragraph goes to the check model, and if that refuses too it comes back as 【未翻：內容過濾】 for the human pass."""
    try:
        return _translate_chunk(k, total, idxs, paras, cfg, glossary, model)
    except RuntimeError as e:
        if not blocked(e):
            raise
    if len(idxs) > 1:
        a, b = idxs[:len(idxs) // 2], idxs[len(idxs) // 2:]
        print(f"  chunk {k}: P{idxs[0] + 1:03d}–P{idxs[-1] + 1:03d} blocked, splitting", flush=True)
        ra, ua = translate_chunk(k, total, a, paras, cfg, glossary, model)
        rb, ub = translate_chunk(k, total, b, paras, cfg, glossary, model)
        return {**ra, **rb}, ub
    if model is None:
        return translate_chunk(k, total, idxs, paras, cfg, glossary, mm.CHECK_MODEL)
    print(f"  P{idxs[0] + 1:03d} refused by both models: left for the human pass", flush=True)
    return {f"{idxs[0] + 1:03d}": "【未翻：內容過濾】"}, {}


FORMULA = re.compile(r"(欲知|不知|未知|畢竟|毕竟|要知)[^。！？]{0,24}[，,]?\s*(且|請|请|再)?(看|聽|听)下(回|文)(分解|便知)[。！]?")


def _translate_chunk(k, total, idxs, paras, cfg, glossary, model=None):
    L = lang(cfg)
    system = (f"你是資深文學譯者，也是有聲書改編者。要把{L['author']}翻成給台灣大人"
              f"睡前聽的中文朗讀稿。\n\n規則：\n{L['rules']}\n\n系列對照表：\n{L['glossary']}\n\n本篇對照表：\n{glossary}")
    want = [f"{i + 1:03d}" for i in idxs]
    # episode 79: M3 drops or merges a different single paragraph out of 38 on every try — keep what came back
    # and ask again only for what is still missing (only complete turns count, so a cut-off answer is never kept)
    acc, todo = {}, list(idxs)
    for attempt in range(5):
        user = f"以下是〈{cfg['title']}〉第 {k}/{total} 部分。請依規則翻譯，只輸出譯文段落。\n\n原文：\n{numbered(paras, todo)}"
        text, usage, stop = mm.m3(system, user, model=model, effort="medium")
        if stop == "end_turn":
            acc.update({g: t for g, t in ((m.group(1), m.group(2).strip()) for m in MARK.finditer(text))
                        if t and g in want and g not in acc})
        missing = [w for w in want if not acc.get(w)]
        if not missing:
            return {w: acc[w] for w in want}, usage
        print(f"  chunk {k}/{total} attempt {attempt + 1}: missing={missing[:8]} stop={stop}", flush=True)
        todo = [int(w) - 1 for w in missing]
    # (764 狄公案四): GONGAN_RULES 6 tells the model to delete a chapter-end 「不知後事如何，且看下回分解」, so a
    # paragraph that is nothing else never comes back — it becomes a scene break (「……」, 0.8 s of silence) instead
    if missing and all(FORMULA.fullmatch(paras[int(w) - 1].strip()) for w in missing):
        print(f"  chunk {k}/{total}: {missing} = chapter-end formula only → 「……」", flush=True)
        return {w: acc.get(w) or "……" for w in want}, usage
    raise SystemExit(f"chunk {k} failed validation after retries")


def selfcheck_chunk(idxs, paras, zh, cfg):
    L = lang(cfg)
    system = (f"你是嚴格的翻譯審稿人。逐段比對{L['name']}原文與中文譯文，只找「意思錯誤」：主詞或人稱錯、把稱呼當主詞、否定反了、"
              f"數字／時間／金額錯、指代錯、{L['slang']}、漏譯或多譯、引號層次錯。語氣與用字風格不算錯。只輸出 JSON 陣列："
              '[{"id":"P012","problem":"一句話說明","fix":"修正後的完整段落譯文"}]；沒有問題就輸出 []。')
    pairs = "\n\n".join(f"【P{i + 1:03d}】\n{L['tag']}: {paras[i]}\nZH: {zh[f'{i + 1:03d}']}" for i in idxs)
    for attempt in range(3):
        try:
            text, usage, stop = mm.m3(system, f"〈{cfg['title']}〉\n\n{pairs}", max_tokens=40000,
                                      model=mm.CHECK_MODEL, effort="medium")     # see mm.CHECK_MODEL
        except RuntimeError as e:
            # episode 64 (Sign of Four, the Andaman passages) — the English side trips MiniMax's input filter
            # (HTTP 500 "new_sensitive (1026)") on every retry, and the whole finished translation was thrown away.
            # The self-check is advisory; human review compares every paragraph to the English anyway.
            if "1026" not in str(e) and "sensitive" not in str(e):
                raise
            print(f"  selfcheck P{idxs[0] + 1:03d}–P{idxs[-1] + 1:03d} blocked by content filter: skipped", flush=True)
            return [{"id": "ALL", "problem": f"self-check blocked by content filter for P{idxs[0] + 1:03d}–P{idxs[-1] + 1:03d}", "fix": ""}]
        try:
            flags = json_block(text)
            return [f for f in flags if isinstance(f, dict) and re.fullmatch(r"P\d{3}", str(f.get("id", "")))]
        except Exception as e:
            print(f"  selfcheck attempt {attempt + 1} unparsable: {e}", flush=True)
    return [{"id": "ALL", "problem": "self-check output unparsable", "fix": ""}]


def normalise(zh):
    zh = zh.replace("！", "。").replace("!", "。")
    cjk = r"[㐀-鿿「」『』]"
    for half, full in ((",", "，"), (";", "；"), (":", "："), ("?", "？")):
        zh = re.sub(rf"(?<={cjk}){re.escape(half)}|{re.escape(half)}(?={cjk})", full, zh)
    zh = zh.replace("。。", "。")
    # Lupin (French): M3 keeps the dialogue dash — 「——你好」, --「你好」 — and turns a ------ rule into ——
    zh = zh.replace("--", "——")
    zh = re.sub(r"^\s*—+\s*(?=「)", "", zh)
    zh = re.sub(r"「\s*—+\s*", "「", zh)
    return "……" if re.fullmatch(r"[—\s]+", zh) else zh


def main():
    ep = Path(sys.argv[1]).expanduser()
    # two queues once translated the same night twice and the later copy landed under a reviewer's feet —
    # never overwrite a reviewed script, and only one translator per episode at a time
    if (ep / "script" / "REVIEW-DONE").exists():
        sys.exit(f"{ep.name}: already reviewed (script/REVIEW-DONE) — refusing to overwrite")
    try:
        (ep / ".translating").mkdir()
    except FileExistsError:
        sys.exit(f"{ep.name}: another translate.py is on it (.translating)")
    import atexit
    atexit.register(lambda: (ep / ".translating").rmdir())
    cfg = json.loads((ep / "episode.json").read_text())
    L = lang(cfg)
    src = glob.glob(str(ep / "source" / f"*.{cfg.get('source_lang', 'en')}.txt"))[0]
    paras = [p.strip() for p in Path(src).read_text(encoding="utf-8").split("\n\n") if p.strip()]
    out = ep / "script"
    out.mkdir(exist_ok=True)
    t0, q0 = time.time(), mm.quota()
    if (out / "outline.json").exists() and json.loads((out / "outline.json").read_text()).get("_doc", "").startswith(
            "10-05 hand-written"):          # (370): M3 refused every outline attempt — a hand-written one is kept
        o = json.loads((out / "outline.json").read_text())
    else:
        o, _ = outline(cfg, paras)
    (out / "outline.json").write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    glossary = "｜".join(f"{g['en']}＝{g['zh']}" for g in o.get("glossary", []) if g.get("en") and g.get("zh"))
    plan = chunks(paras, L["chunk"], L["size"])
    if cfg.get("source_lang") == "zh":            # 霍桑探案: the original is read as written
        zh = {f"{i + 1:03d}": t.translate(str.maketrans("“”‘’", "「」『』"))   # the speaker tagger reads 「」
              for i, t in enumerate(to_traditional(paras))}
        plan = []
    else:
        with ThreadPoolExecutor(max_workers=3) as pool:
            parts = list(pool.map(lambda a: translate_chunk(a[0], len(plan), a[1], paras, cfg, glossary)[0],
                                  [(k, idxs) for k, idxs in enumerate(plan, 1)]))
        zh = {k: v for part in parts for k, v in part.items()}
    # episode 16 came back with 48 paragraphs still in English and a clean self-check. Retry those once;
    # if any survive, the episode is marked translated-incomplete so review and production both notice.
    def untranslated():
        # more Latin letters than CJK characters, and at least a short sentence of them = not translated
        # (the ARAT / BALLARAT puns of episode 4 are single words and stay under the 12-letter floor)
        def bad(t):
            if cfg.get("source_lang") == "ja":        # kana left in the Chinese = that paragraph was not translated
                return len(re.findall(r"[ぁ-ゟ゠-ヿ]", t)) >= 6
            latin = len(re.findall(r"[A-Za-z]", t))
            return latin >= 12 and latin > len(re.findall(r"[㐀-鿿]", t))
        return [i for i in range(len(paras)) if bad(zh.get(f"{i + 1:03d}", ""))]
    if untranslated():
        print(f"retrying {len(untranslated())} untranslated paragraphs", flush=True)
        zh.update(translate_chunk(0, 1, untranslated(), paras, cfg, glossary)[0])
    missing = untranslated()
    with ThreadPoolExecutor(max_workers=3) as pool:
        flags = [f for fl in pool.map(lambda idxs: selfcheck_chunk(idxs, paras, zh, cfg), plan) for f in fl]
    rows = [{"id": f"P{i + 1:03d}", "en": p, "zh_raw": zh[f"{i + 1:03d}"], "zh": normalise(zh[f"{i + 1:03d}"])}
            for i, p in enumerate(paras)]
    if cfg.get("source_lang") == "fr":
        # (215): M3 sometimes keeps a French dash line as 「——話……」 with no quotes at all. Wrap it so the line is
        # at least spoken as dialogue; the reviewer moves a « dit-il » tail out of the quotes.
        for r in rows:
            if re.match(r"\s*(—|--|«)", r["en"]) and "「" not in r["zh"]:
                body = re.sub(r"^\s*—+\s*", "", r["zh"])
                r["zh"] = f"「{body}」" if body else r["zh"]
    (out / "script.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "script-zh.md").write_text("\n\n".join(f"【{r['id']}】{r['zh']}" for r in rows) + "\n", encoding="utf-8")
    (out / "flags.json").write_text(json.dumps(flags, ensure_ascii=False, indent=1), encoding="utf-8")
    cfg["teaser"] = o["teaser"]
    cfg["intro"] = show.intro(cfg["source_phrase"], o["teaser"], cfg.get("narrator", "watson"))
    cfg["outro"] = show.outro(to_be_continued=cfg.get("part", 1) < cfg.get("parts", 1),   # novels: every part but the last
                              series=cfg.get("series"))
    cfg["scenes"] = [{"start": s["start"], "chapter": s["chapter"]} for s in o["scenes"]]
    cfg["status"] = "translated-incomplete" if missing else "translated"
    if missing:
        print(f"WARNING {ep.name}: still untranslated {[f'P{i + 1:03d}' for i in missing]}", flush=True)
    (ep / "episode.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    cjk = sum(len(re.findall(r"[㐀-鿿]", r["zh"])) for r in rows)
    print(f"{ep.name}: {len(paras)} paragraphs, {len(o['scenes'])} scenes, {len(flags)} self-check flags, "
          f"{cjk} CJK chars, {time.time() - t0:.0f}s; quota {q0} → {mm.quota()}", flush=True)


if __name__ == "__main__":
    main()
