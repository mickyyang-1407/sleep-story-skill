> 分享版說明：「量產庫」＝製作者的專案資料夾；這份包的工具在`tools/`，製作者本機才有的檔案（帳本、排程、各季設定檔）不在包內

# 10 Shorts

- 每集三支：a懸念、b反轉、c謎題；≤60秒、不爆雷；「相關影片」連回長片
- 規格正本：量產庫`shorts/SELECTING.md`（選段）、`shorts/SOP.md`（製作）
- **第103夜起用§v2**：第一句就是矛盾、一支一個懸念、結尾卡只放一個問題＋一行中性導流（不寫時間、不寫「已上線」）；1–102的成品不動
- 新的一季或新寫法的第一集，先放`shorts/drafts/`給

```bash
# 寫好shorts/NN.json後
python3 shorts_check.py NN # 必須OK：時間對齊字幕、≤55.5 s、鉤子兩行各≤8字、標題說明格式
python3 shorts.py NN # 或交給背景shorts-watch.sh（夜窗）
```
- 輸出`完成Shorts/第NN夜-篇名-{a懸念,b反轉,c謎題}.{mp4,txt,zh-Hant.srt}`；1080×1920、−14 LUFS／≤−1.5 dBTP
- ⚠️ `shorts_check.py`第16行的`CHANNEL`還是舊handle、舊`shorts/01.json`等早期稿裡有「今晚10點」這類過期導流：寫新稿或對外示範時不要沿用
- 上傳：Shorts只上傳配樂那一套，不把無配樂版另做一套
- 成效紀錄：`shorts/V2-OBSERVATION.md`
