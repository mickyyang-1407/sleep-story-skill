---
name: sleep-story
description: 把公版推理小說做成分角色睡前廣播劇影片的完整流程（來源與權利→翻譯改寫→對照原文審稿→說話者與選聲→分角色配音→插圖→字幕組片混音→配樂／無配樂兩版→品管→封面文案→Shorts→上架包）。使用者說「做一集睡前故事」「把這篇小說做成睡前廣播劇」「睡前推理廣播劇」時使用
---

# 睡前推理廣播劇製作流程（枕邊偵探社分享版）

這是「枕邊偵探社」（https://www.youtube.com/@PillowMysteries ）實際在用的製作流程，從製作者的本機正本匯出
- 成品請放**你自己的頻道**；這份包不含任何上傳工具，也不會連到製作者的頻道
- 文中的「製作者」＝做決定的人（選聲音、確認上架），「Codex」＝另一個AI助手（畫封面底圖、上傳），換成你自己的分工即可
- 開始前先讀同一層的`README.md`：需要自備哪些帳號、工具和素材

## 流程（13步）

| # | 步驟 | 細節 | 這份包裡的工具 |
|---|---|---|---|
| 1 | 原著、版本、公版／授權、插畫來源 | `references/01-source-rights.md` | 自己準備`source/*.txt`＋`episode.json`（範本在`templates/`） |
| 2 | 翻譯＋睡前改寫 | `references/02-translate-review.md` | `tools/translate.py`（需MiniMax key） |
| 3 | 對照原文審稿 | 同上 | `tools/review.py`、`apply_fixes.py`、`fixkit.py`、`trim_tail.py` |
| 4 | 說話者標註、選角 | `references/03-cast-voice.md` | `tools/speakers.py`、`drama_tts.py --dry-run` |
| 5 | 分角色配音 | 同上 | `tools/drama_tts.py`（MiniMax）、`bailian_tts.py`（百鍊，選用） |
| 6 | 插圖 | `references/04-art.md` | `tools/fetch_art.py`、`art.py`（本機生圖工具不在包內） |
| 7 | 字幕、組片、混音、兩個版本 | `references/05-assemble-qc.md`；配樂整理`references/09-suno-music.md` | `tools/assemble.py`（`--nomusic`出無配樂版）、`tools/suno_master.py`（把錄回來的音樂切曲、剪長音、做母帶） |
| 8 | 品管 | 同上 | `tools/qc.py`（需whisper） |
| 9 | 封面、標題、文案 | `references/06-cover-copy.md` | `tools/cover.py`、`package.py` |
| 10 | Shorts | `references/07-shorts.md` | `tools/shorts.py`、`shorts_check.py` |
| 11–13 | 收集、防重複、上傳 | `references/08-collect-upload.md` | **不在包內**：製作者的帳本與上傳流程綁原本的頻道；你自己用`package.py`的上架包手動上傳 |

**自己的主題也可以**：自己寫中文稿、單人旁白，做成影片和開車／睡前聽的音檔，見`references/10-own-topic-audio.md`

`tools/produce.py`只串6–8步加文案，不是一條指令全包；1–4步要先做完、`episode.json`的`status`設成`reviewed`

## 第一次使用：先跑不花錢的檢查
```bash
cd sleep-story-share
python3 -m pip install -r requirements.txt
python3 tools/review.py examples/night-01-excerpt | head -20
python3 tools/speakers.py examples/night-01-excerpt --en | head -20
python3 tools/drama_tts.py examples/night-01-excerpt --dry-run
python3 tools/art.py examples/night-01-excerpt
```
這幾步都不打API；`CHECKS.md`列了製作者匯出時實際跑過的結果

## 做一集（真的要花TTS／翻譯額度）
```bash
cp .env.example .env    # 填你自己的key，然後 set -a; source .env; set +a
E=episodes/01-my-story  # 照templates/建好source與episode.json
python3 tools/translate.py $E
python3 tools/review.py $E | less          # 每段都要對照原文審，修正見references/02
python3 tools/speakers.py $E --en          # 手寫script/speakers.json＋cast.json
python3 tools/drama_tts.py $E --dry-run
# episode.json status → reviewed
```
接下來分兩種，**先決定再花配音錢**：

**A．有自備配樂（配樂版＋無配樂版）**
```bash
export SD_MUSIC_BED=/path/to/your-music.flac   # 沒設這個不會報錯：「配樂版」會悄悄做成沒有配樂的檔
SD_QUOTA_FLOOR=0 python3 tools/produce.py $E   # 插圖→配音→配樂版組片→品管→文案，成功把status設produced
python3 tools/assemble.py $E --nomusic         # 再出無配樂版
```

**B．只要無配樂版（不要跑produce.py）**
```bash
export SD_QUOTA_FLOOR=0
python3 tools/art.py $E
python3 tools/drama_tts.py $E                  # 花配音額度
python3 tools/assemble.py $E --nomusic         # → *-nomusic.mp4、build/assemble-report-nomusic.json
python3 tools/qc.py $E                         # → build/qc-report.json
python3 tools/package.py $E                    # 文案
```
A做完確認`build/assemble-report.json`的`music.on`是true，才是真的有配樂

B做完要自己看兩份報告：`build/assemble-report-nomusic.json`的`aac.ok`是true、`build/qc-report.json`每個抽樣段`ends_ok`是true

B不會把`status`改成`produced`，也沒有配樂版，不要說成兩版都完成

先用一小段（幾百字）試跑，量一次實際用量再做整集

## 中斷了怎麼接
- 配音有句子快取（`audio/calls/`），重跑不會重複付費
- **翻譯沒有**：重跑`translate.py`會重翻全部段落並覆寫`script.json`；已經審過或改過字，先備份再決定重做哪幾段
- 細節見各步references的「續做」

## 狀態分開講
審稿完≠配音完≠組片＋品管過≠兩個版本都有≠已上傳；每一層各自看產物，不要因為資料夾存在就當完成
