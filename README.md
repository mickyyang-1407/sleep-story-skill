# 睡前推理廣播劇製作包（枕邊偵探社分享版）

把公版推理小說做成「分角色配音＋插圖＋字幕」的睡前廣播劇影片，配樂版和無配樂版各出一支，再切三支Shorts

- 作品示範：[枕邊偵探社](https://www.youtube.com/@PillowMysteries)
- 這是本機分享封裝，從製作者的skill正本自動匯出（`EXPORT.json`記匯出時間與來源檔hash）
- **不是一鍵完成**：翻譯、配音要用你自己的付費帳號；審稿、選聲音、封面鉤子要人看

## 這份包有什麼
| 資料夾 | 內容 |
|---|---|
| `SKILL.md`、`references/` | 給Claude Code／Codex讀的流程說明（13步） |
| `tools/` | 製作者量產線實際在用的程式，只收單集製作需要的那些；匯出時把寫死的路徑和金鑰讀法改成讀環境變數 |
| `cast-default.json` | 全系列選角（聲音名稱是MiniMax／百鍊的公開預設聲音） |
| `templates/` | `episode.json`、`cast.json`、`shorts.json`範本 |
| `examples/night-01-excerpt/` | 〈紅髮會〉開頭12段：英文原著（公版）、AI翻譯＋審過的中文、說話者、選角、一張Sidney Paget原刊插畫（公版） |
| `.env.example` | 要填的環境變數 |
| `CHECKS.md` | 匯出時實際跑過的離線檢查與結果 |

## 沒有包含（要自己準備或自己決定）
- 金鑰、帳號：MiniMax（翻譯＋配音）、百鍊（選用的旁白）
- 配樂：製作者用自己的音樂，不在包內，有授權的音樂就設`SD_MUSIC_BED`再跑`produce.py`；沒有配樂就**不要跑`produce.py`**：它一定先做「配樂版」，沒設配樂不會報錯，而是做出檔名叫preview、其實沒有配樂的檔（`build/assemble-report.json`的`music.on`是false），還會把狀態標成produced；改走`SKILL.md`「做一集」的B路線，只出無配樂版
- 本機生圖（ComfyUI＋Qwen-Image）：不在包內；可以只用公版原刊插畫
- 上傳工具、上傳帳本、自動排程、收集腳本：綁製作者頻道，不在包內
- 封面底圖：製作者請另一個AI畫無字底圖再用`cover.py`疊字；你可以用任何有權使用的圖
- 成品影片、音檔

## 需要安裝
| 東西 | 用途 | 備註 |
|---|---|---|
| Python 3.10以上＋`requirements.txt` | 全部工具 | numpy、Pillow |
| ffmpeg／ffprobe | 配音後處理、組片、混音 | 需要能輸出AAC |
| `opencc`指令 | 字幕繁簡轉換、品管比對 | macOS：`brew install opencc` |
| `whisper`指令（openai-whisper） | 品管把聲音轉回文字 | 路徑可用`WHISPER_BIN`指定 |
| macOS | 片頭、場景、片尾畫面（`art.py`） | **目前只在macOS驗證過**：`art.py`直接用macOS系統的宋體（Songti.ttc）與Baskerville，路徑寫死在`/System/Library/Fonts/Supplemental/`；蘋方可用`SD_FONT_PINGFANG`指定，其他系統要自己改`art.py`的字型路徑，沒有測過 |
| Noto Sans CJK TC（Black、Bold） | 封面、Shorts | 放`~/Library/Fonts/`或用`SD_FONT_NOTO_BLACK`／`SD_FONT_NOTO_BOLD`指定 |
| `nice`指令 | 降低組片優先序 | macOS／Linux內建 |

## 授權
- 程式與文件：MIT（`LICENSE`，sleep-story-skill contributors）
- 範例裡的公版原著與插畫、外部服務、字型、節目名稱不在MIT範圍：見`THIRD_PARTY_NOTICES.md`

## 從哪裡開始
1. 讀`SKILL.md`
2. 跑`SKILL.md`裡「先跑不花錢的檢查」那四行，確認環境
3. 選一篇你所在地區已進入公版的作品，照`references/01-source-rights.md`確認來源
4. 先用幾百字試跑翻譯和配音，看實際用量，再做整集

## 改成你自己的節目
工具裡寫著製作者的節目名，做之前先改掉：
- `tools/show.py`：`CHANNEL`（節目名）和開場、結尾台詞
- `tools/shorts.py`：Shorts畫面上的節目名（搜尋「枕邊偵探社」）
- `tools/season.py`：系列名稱與播放清單名
- `episode.json`的`series`、`intro`、`outro`

## 自己要確認的
- 公版判斷依你播出的地區；製作者依台灣規則，不代表全球適用
- 響度目標（長片−14 LUFS、真峰值≤−1.0 dBTP）是製作者自己的交付標準，不是平台強制規格
- 影片說明寫清楚：旁白是AI語音合成、插圖哪些是原刊公版哪些是AI繪製
