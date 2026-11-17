# 匯出時實際跑過的檢查（2026-11-17，macOS）

環境：解壓到全新資料夾，`env -i HOME=<空資料夾> PATH=/opt/homebrew/bin:/usr/bin:/bin`，**沒有任何金鑰、沒有製作者的設定檔**

| 指令 | 結果 |
|---|---|
| `python3 tools/review.py examples/night-01-excerpt` | exit 0，印出P001–P012英中對照 |
| `python3 tools/speakers.py examples/night-01-excerpt --en` | exit 0，印出說話者草稿＋英文 |
| `python3 tools/drama_tts.py examples/night-01-excerpt --dry-run` | exit 0：`3 segments, 16 calls (16 distinct), 2 voices: Gentleman, Reliable_Executive`（不打API） |
| `python3 tools/art.py examples/night-01-excerpt` | exit 0，產出`art/frames/title.png`、`scene-01.png`、`end.png` |
| `python3 tools/bed_check.py <20秒正弦波>` | exit 0，`ok` |
| `python3 tools/srtfix.py <含單獨」與零長度條目的字幕>` | exit 0，`3 → 2 cues`，」併回前一條 |
| `SD_QUOTA_FLOOR=0 python3 tools/produce.py <範例副本>` | 畫完插圖→配音預檢→印`quota not queried (SD_QUOTA_FLOOR=0)`→在第一個配音請求前停下：`MINIMAX_API_KEY is not set`，exit 1（沒有金鑰就不會送出任何請求） |
| `SD_QUOTA_FLOOR=0`時把`mm.call`換成會報錯的假函式再呼叫`mm.quota()` | 回`{"checked": False, "note": "quota not queried (SD_QUOTA_FLOOR=0)"}`，假函式被呼叫0次（完全不查額度） |
| 沒設`SD_QUOTA_FLOOR`時同樣呼叫 | 假函式被呼叫，網址是中國站Token Plan額度端點（證明上一條的檢查不是永遠綠燈） |
| `import translate, qc, assemble, package, cover, shorts, shorts_check` | 全部可匯入；`qc.WHISPER`＝`whisper`、Shorts頻道網址＝`.env`裡的設定 |

## 沒有在這裡驗證的（需要你的帳號或較長運算）
- 真的翻譯、配音（要MiniMax／百鍊額度）
- 組片、混音、品管、封面、Shorts渲染（要先有配音）
- 製作者那邊，這些步驟在量產線上已經做過數百集；但這份分享包本身還沒完整跑過一集
