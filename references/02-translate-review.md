> 分享版說明：「量產庫」＝製作者的專案資料夾；這份包的工具在`tools/`，製作者本機才有的檔案（帳本、排程、各季設定檔）不在包內

# 2–3 翻譯、睡前改寫、對照原文審稿

## 翻譯
```bash
python3 translate.py $E # 大綱→三路並行逐段翻譯→自查；輸出script/script.json、flags.json、script-zh.md
```
- `script.json`是一個list，每段`{"id":"P001","en":…,"zh_raw":…,"zh":…}`；段落編號必須跟原文對齊，後面的說話者、場景、插圖都靠它
- 模型：MiniMax（`mm.py`，`SD_M3_MODEL`預設`MiniMax-M3.1-Flash`）；103夜以後的季別由claude-team翻譯（`team_translate.py`，本機Team席）。不要自己換provider
- 日文來源在`episode.json`設`source_lang: ja`
- 已知錯誤處理（程式內建）：整段不翻會自動重翻；英文觸發MiniMax輸入過濾（HTTP 500 `1026`）時只跳過那批自查，在`flags.json`記一筆`ALL`，那些段落人工細對
- 睡前改寫：暴力細節放緩，但**不刪情節、不改結局**；雙關要為耳朵改寫

## 審稿（每一段都要對照英文）
```bash
python3 review.py $E | less # 英中對照
```
- 修正寫成JSON用`apply_fixes.py $E fixes.json`套用；常見系統性錯誤用`fixkit.py`（`e/z/g`→`nest`→`unclose_auto`）
- 書末夾帶下一篇羅馬數字或出版社廣告：`trim_tail.py $E`（scenes／speakers指到被刪的段會拒絕）
- 各季審稿規範：`<季>-REVIEW-BRIEF.md`；審完放`script/REVIEW-DONE`
- **誰審的要寫清楚**：大部分由AI子代理照brief審、主session抽查；不能寫成「每段都由

## 審稿錯型清單（完整版在`HANDOFF-2026-09-25.md` §8）
- 引號層級幾乎每集都錯：長篇轉述結束後外層不關、多段連續發言中途收引號、旁白被包成引號 → `fixkit.nest`依英文“ ‘重建；**45集以後英文是直引號`"`，fixkit只認彎引號，要先轉**
- 意思翻反、人稱錯（我／她、we／I）、稱呼語被當成主詞
- 問號被吞成句號
- 簡體字混入：用`opencc -c s2tw`**比對**逐字看，不要直接整篇轉
- 地名、貨幣、俚語、時代（sovereign＝金鎊、half a crown、equinoctial gales＝秋分前後暴風）
- 全集譯名一致：長篇的跨集譯名表放`novel-cast/<書名>.json`的`_names`
- 有一段只寫「（保留）不作更動。」＝其實沒翻，漏翻偵測抓不到（它只看英文字母比例）
- AI自查的疑點約一半是誤報，回傳0個疑點也不代表沒問題

## 不要做
- 不對繁中譯文跑OpenCC `s2twp`（會改壞用字）
- 不覆蓋已套用的修正；重跑翻譯前先確認哪些段落已有人改過字

## 續做
- **翻譯沒有段落快取**：`translate.py`重跑會重新做大綱、重翻全部段落，並覆寫`script/script.json`與`episode.json`的設定；只有`script/REVIEW-DONE`存在時才拒寫（早期集數沒有這個檔）
- 已有譯稿或人工改字：先備份整個`script/`與`episode.json`，對照確定要重做哪些段落；沒確認之前不要重跑`translate.py`
- 審稿修正都在`fixes-*.json`，翻譯重做後可以重套（重套前先看段落編號是否還對得上）
