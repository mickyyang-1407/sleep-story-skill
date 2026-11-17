> 分享版說明：「量產庫」＝製作者的專案資料夾；這份包的工具在`tools/`，製作者本機才有的檔案（帳本、排程、各季設定檔）不在包內

# 4–5 說話者、選角、分角色配音

## 說話者標註（規範正本：量產庫`TAGGING.md`）
```bash
python3 speakers.py $E --en # 每段帶「」的段落：猜測、編號過的中文、英文原文；猜測不可信
```
- `script/speakers.json`：`{"P005":"holmes","P050":["king","holmes"],"P242":["holmes",null]}`；字串＝整段同一人，list＝每個頂層「」依序，`null`＝旁白念，沒列＝旁白
- 不標（留給旁白）：詞語、招牌字、報紙／告示／廣告原文、狀聲詞；劇情中被念出來的信由寫信的人念
- 跨段落長對白每一段都要標同一個人；群眾用`crowd`；角色鍵英文小寫
- 喬裝未揭曉的角色不能用本尊的聲音（避免洩底）

## 選角
- 全系列：`cast-default.json`
 - `fixed`：旁白、福爾摩斯等固定聲音
 - `recurring`：常駐角色，第一次出場決定後不再換
 - `pools`：一次性角色候選（`man_mid` `man_young` `man_old` `man_rough` `woman_young` `woman_mid` `woman_old` `boy` `girl`）
 - `season_narrator`：各季旁白
- 每集：`script/cast.json`，例：`{"wilson":"pool:man_old","clay":{"voice":"lengdan_xiongzhang","emotion":null}}`
- 長篇跨集角色：`novel-cast/<書名>.json`（只分配有跨集台詞的主要角色，留幾個男聲給一次性角色）
- 旁白和主角的聲音不能指派給別人；一次性角色不要挑到常駐聲
- 檢查（不花錢，每集必過）：
```bash
python3 drama_tts.py $E --dry-run # 擋：引號數對不上、角色沒聲音、池子用完、段落編號不存在
python3 cast_consistency.py # 跨集同角同聲（按需）
```

## 配音
- `drama_tts.py $E`：MiniMax `speech-2.8-hd`、speed 0.85、句間0.5 s、段間1.5 s、場景間3.5 s；旁白／福爾摩斯`emotion: calm`，配角不給emotion
- 百鍊：聲音寫`bailian:<voice>`會自動轉`bailian_tts.py`（每句一個請求、句間補靜音；24 kHz→44.1 kHz用swr `filter_size=64`）
- **音量對齊**：每集每個聲音對齊旁白中位響度，寫在manifest的`level`；新聲音進來先量
- **快取**：每個請求存`audio/calls/<sha1>`；只改少數段落重跑時，沒變的句子不再付費
- 每分鐘上限：MiniMax回`1002`／`1039`要退避（程式已處理）；`2067`＝Token Plan用量上限，重試沒用
- 只有「……」的台詞自動變0.8秒靜音；日文假名一律不留

## 新聲音
新常駐角色或新一季旁白：先用量產庫`audition/`做試聽包，交
