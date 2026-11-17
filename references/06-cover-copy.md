> 分享版說明：「量產庫」＝製作者的專案資料夾；這份包的工具在`tools/`，製作者本機才有的檔案（帳本、排程、各季設定檔）不在包內

# 9 封面、標題鉤子、上架文案

## 封面
1. 無字底圖：把該集prompt照`covers/PROMPTS-*-v5.md`的格式寫好，交Codex畫成`covers/NN.png`（左45%深色留白、好奇不驚恐、長篇同色系）；亂步以後各季用`rampo_cover.py brief/draw`
2. 鉤子：寫進`covers/hooks.json`的`big`（`"兩行|用直線分開"`，每行≤7字最好）
3. 疊字：`python3 cover.py NN`（紅標籤「第N夜｜篇名」＋兩行鉤子＋彎月「助眠廣播劇」）
- 字體：`~/Library/Fonts/NotoSansCJKtc-Black.otf`、`-Bold.otf`

## 驗收（每張都看，不抽查）
- 9張一頁總表＋左半裁切看字有沒有壓到臉
- 鉤子要在`script/script-zh.md`裡grep得到、不直指破案線索、不跟別集重複句型
- 第一行太長會把兩行一起縮小
- 封面插圖是AI繪製，對外說明要寫清楚

## 文案
`python3 package.py $E`：標題（以鉤子開頭）、說明、章節、標籤、字幕包、上架前檢查清單
- 說明欄不能出現`<#0.6#>`這類停頓標記（已修過一次）
- 改標題或鉤子：改`hooks.json`→`cover.py NN`→`package.py $E`→`collect.sh`；已上傳的下次會變成`EDIT`
