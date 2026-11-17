> 分享版說明：「量產庫」＝製作者的專案資料夾；這份包的工具在`tools/`，製作者本機才有的檔案（帳本、排程、各季設定檔）不在包內

# 11–13 收集、帳本防重複、經授權上傳

## 收集成上架包
```bash
zsh collect.sh # 背景--watch每10分鐘跑；急的時候手動
```
- 輸出`完成影片/`、`完成影片-無配樂/`、`完成Shorts/`、`完成Shorts-無配樂/`與各自的`manifest.json`
- manifest的`file_version`（影片檔版次）和`meta_version`（文案版次）分開；`ready`＝可以上傳
- 讀manifest找缺件，不要以資料夾存在當作完成

## 帳本與上傳計畫（Codex跑，Claude只讀）
```bash
python3 tools/upload_plan.py plan # ⚠️會寫出upload-plan.json；沒有不寫檔的乾跑模式
python3 tools/upload_plan.py record <item> <影片ID>
python3 tools/upload_plan.py retire <舊影片ID>
python3 tools/upload_plan.py edited <item>
```
| 動作 | 意思 |
|---|---|
| `NEW` | 還沒上傳過 |
| `REPLACE` | 檔案換版且還沒公開（或帳本標`replace_approved`）：上新的、舊的設私人 |
| `EDIT` | 只改標題／說明／標籤／縮圖／字幕 |
| `HOLD` | 已公開又換檔：問製作者 |
| `WAIT` | 還沒準備好 |
- 帳本`youtube-ledger.json`只用指令改，不手改
- 全面停止上傳：建`UPLOAD-HOLD.txt`
- 兩條線：`long-NN`配樂版＋唯一一套Shorts、`nm-long-NN`無配樂版（標題帶「・無配樂」、自己的播放清單）

## 上傳（只有
- 規則正本：量產庫`UPLOAD-FOR-CODEX.md`；YouTube與B站輪流，每批先重跑plan
- 上傳前現場核對頻道「枕邊偵探社」、Channel ID `UC0tjyrmgmp8kLCvQn2rVVNA`
- 做完要回讀平台狀態（排程／公開／字幕），從帳本和平台實況續做，不重新上傳
- Claude不按上傳、不刪影片
