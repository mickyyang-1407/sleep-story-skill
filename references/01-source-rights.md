> 分享版說明：「量產庫」＝製作者的專案資料夾；這份包的工具在`tools/`，製作者本機才有的檔案（帳本、排程、各季設定檔）不在包內

# 1 原著、版本與權利

## 要交付什麼
- `episodes/NN-slug/source/*.txt`（原文，段落之間空一行）＋`episode.json`（標題、季別author、場景、旁白參數、狀態）
- 每一份原文和插畫都要寫得出「從哪裡來、為什麼可以用」

## 現有工具（量產庫）
| 來源 | 工具 | 備註 |
|---|---|---|
| 福爾摩斯全集（Project Gutenberg） | `series.py list`／`series.py extract N` | 56短篇＋4長篇切成約9千英文字一段，不切在章節中間 |
| 其他各季 | `<季>.py extract`（`rampo.py`、`christie.py`、`brown.py`、`lupin.py`、`hanshichi.py`、`gongan.py`…） | 日文來源Aozora Bunko、中文來源zh.wikisource（`_gongan_fetch.py`，已是繁體，不跑OpenCC）、法文`fetch_wikisource.py` |
| 季別設定 | `season.py`的`SEASONS` | `label`（觀眾看到的「亂步第N夜」）、`first`（起始集號）、`gate`（上傳閘門檔）、`not_before`（公版日）、`art`（畫風）、`playlist` |

## 權利判斷
- **公版日以播出地區為準**：`season.py`的`not_before`是既有的本機閘門（例：阿嘉莎2027-01-01前不公開），實際權利依播出地區另外查核，**不保證全球適用**；新的一季先查作者卒年與首刊年，再決定`not_before`
- **插畫另外判**（`HOLMES-ART-PLAN.md`）：首刊≤1930且畫家卒年≤1955才收；Frank Wiles、H. M. Brock、J. R. Flanagan不收
- 出處寫進該集`art/CREDITS.md`，影片片頭小字與上架文案的`art_credit`也要對得上
- 上傳閘門：`<季>-APPROVED.txt`存在才放行

## 檢查
- `episode.json`欄位齊：`collection`、`narrator`、`source_phrase`、`teaser`（第1集舊格式曾缺，`package.py`會KeyError）
- 長篇：`novel`／`part`／`parts`／`chapters`有值，除了最後一段都會接「下一個夜晚，我們接著說」

## 續做
`extract`遇到已存在的集數會跳過，不會覆蓋；要重抓先手動備份那一集
