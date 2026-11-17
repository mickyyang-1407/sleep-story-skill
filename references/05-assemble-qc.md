> 分享版說明：「量產庫」＝製作者的專案資料夾；這份包的工具在`tools/`，製作者本機才有的檔案（帳本、排程、各季設定檔）不在包內

# 7–8 字幕、組片、混音、雙版本、品管

## 組片
```bash
python3 assemble.py $E # 配樂版 → NN-…-preview.mp4、build/assemble-report.json
python3 assemble.py $E --nomusic # 無配樂版 → NN-…-nomusic.mp4、build/assemble-report-nomusic.json
python3 assemble.py $E --reuse-video # 只改聲音時沿用畫面
```
- 串旁白、繁簡字幕、章節、影片；只有標點的字幕條目（例如單獨一個」）併回前一條、零長度條目修掉，由`srtfix.py`處理（已內建，也可單獨跑在舊檔上）
- **配樂**：`bed_for(集數)`依`ROTATION`從`music/pool/`輪播；對白以下16.5 LU（`MUSIC_REL`），講話時sidechain 3:1（`DUCK_RATIO`）；`SD_MUSIC_BED=<檔>`可指定單一配樂
- 新配樂進pool前先跑`bed_check.py <檔>`：exit 1＝有和弦凍住的長音要剪
- 配樂從哪來、怎麼母帶、怎麼指定單一配樂：`09-suno-music.md`
- **響度（本專案交付目標）**：長片−14 LUFS±0.5、AAC真峰值≤−1.0 dBTP；`master_pass`補不到時加補差增益＋alimiter；AAC過衝會自動降master TP重封
- 兩版各有自己的report；**單版成功不等於兩版都完成**
- 版本路徑與「是否為現行設定」：`variant.py`

## 品管
```bash
python3 qc.py $E # 語速異常＋whisper轉回文字比對（CER）→ build/qc-report.json
```
- produce判定：AAC ok＋每個抽樣段`ends_ok`＋轉回字數≥原文90%才算`produced`
- 紅燈**先懷疑誤判**：whisper在最後30秒幻聽「请不吝点赞」（已用`cut_tail`處理）、數字被寫成阿拉伯數字、逐字母念的密碼
- 真的缺字：對照原音和原稿，只修受影響的句段，再重跑相關檢查；不要只看到PASS就結案
- 百鍊旁白集CER約0.038–0.054，MiniMax集約0.05–0.06（紀錄）

## 坑
- 這台ffmpeg沒有drawtext／subtitles／ass → 畫面上的字一律PIL疊透明圖層
- loudnorm在TP做不到時會默默改動態模式把整段壓低 → 配樂用純增益＋alimiter
- 封裝時`-shortest`會被字幕軌截短 → 用`-t total`
- 同時組裝太多集會把load推到500 → produce有組裝槽`ASSEMBLERS`
- 換配樂／改音量：`remix.py`只重做「不是目前設定」的版本；重做期間manifest的`ready`是false
