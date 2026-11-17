> 分享版說明：「量產庫」＝製作者的專案資料夾；這份包的工具在`tools/`，製作者本機才有的檔案（帳本、排程、各季設定檔）不在包內

# 6 插圖

## 兩種來源
| 來源 | 工具 | 用在 |
|---|---|---|
| 原刊插畫（Wikimedia Commons公版） | `fetch_art.py $E`、福爾摩斯照劇情換圖`holmes_plates.py`（規劃`HOLMES-ART-PLAN.md`） | 福爾摩斯、早期季別 |
| 本機生圖（ComfyUI＋Qwen-Image） | `qwen_art.py $E`（每集≤10張） | 亂步大正雜誌鋼筆畫、凡斯季`anime90s`等，由`season.py`的`art`決定 |
- `art.py $E`把每張圖調成暗暖棕色（彩色畫風只壓暗）＋產出標題卡、結尾卡、縮圖草稿到`art/frames/`；**每次都重畫全部畫格**，所以`produce.py`只在配音前畫
- `episode.json`的`scenes[].art`與`art_cues[]`決定哪一段配哪張圖；scenes保持8–14個

## 規則
- 每張圖寫出處：原刊插畫寫畫家與年份（例：Sidney Paget，1891，公版），AI圖標「本頻道AI繪製」（`art_credit`）
- Wikimedia會回429：抓原圖、每張間隔10秒、照`Retry-After`等
- Qwen在動畫風畫不出空景（一定塞人），提示詞每景要1–2人
- 生圖是重運算：只在夜窗跑；共用的ComfyUI會被多張參考圖弄掛（見全域corrections）

## 檢查
`art/ART-DONE`、`art/frames/title.png`存在；抽看contact sheet，畫面要對得上那段劇情
⚠️ 第1集的`art/preview-sheet.jpg`是舊版（寫「雨聲」、有缺字方塊），不要拿來當示範圖
