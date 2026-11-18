# AGENTS.md — 出貨標籤 QR 與設備叫修系統

這份檔案是給 AI coding agent（Claude Code、Codex 等）看的工作守則。開始任何工作前先讀完本檔，再依「文件地圖」讀對應的規格。

## 專案是什麼

設備供應商的內部工具，兩件事：

1. **出貨標籤**：每台設備一張小標籤，上面有 QR 和序號、型號、叫修電話。QR 內含離線可讀的基本資料。
2. **叫修系統**：QR 最後可多帶一行報修網址。客戶點開就能線上報修，後台管理工單、派工、完修紀錄。

目前狀態：第一階段的程式（P1-01 ~ P1-08）已完成並通過自動化測試，P1-09 實機掃描測試待使用者執行。接下來依 `docs/06-phases.md` 繼續。

## 文件地圖

| 檔案 | 內容 | 什麼時候讀 |
|---|---|---|
| `docs/00-how-to-use.md` | 使用者如何用這套文件指揮 AI 開發、每階段的起手指令 | 使用者看；agent 可略過 |
| `docs/01-product-spec.md` | 角色、流程、功能需求（含編號 FR-xx） | 做任何功能前 |
| `docs/02-architecture.md` | 技術選型、目錄結構、部署、安全 | 建立或改動專案結構前 |
| `docs/03-data-model.md` | 資料表、欄位、工單狀態機 | 動到資料庫或工單邏輯前 |
| `docs/04-qr-label-spec.md` | QR 內容格式、標籤版面、密度規則 | 動到 QR 或標籤前 |
| `docs/05-routes.md` | 頁面與 API 路由、權限 | 新增或修改路由前 |
| `docs/06-phases.md` | 分階段任務清單與驗收條件 | 每次開工先看目前階段 |
| `docs/07-testing.md` | 測試策略與必測案例 | 寫功能的同時 |
| `docs/08-decisions.md` | 已定案的決策與未決事項 | 遇到規格沒寫清楚的地方 |

規格之間有衝突時，以 `docs/08-decisions.md` 為準，並回報給使用者。

## 不可違反的規則

這幾條是使用者明確要求的，違反就是做錯：

1. **一台設備一張 QR。** 不可把多個序號塞進同一個 QR。
2. **QR 必須離線可讀。** 型號、序號、叫修電話一定以純文字寫在 QR 裡。報修網址只是附加的一行，不可把 QR 改成「只有網址」。
3. **標籤上只印三項：序號、型號、叫修電話。** 規格、出貨日期、訂單號不印在標籤上，只放在 QR 內（依勾選）。
4. **標籤是小長方形**（左 QR、右小表格），不是 A4 大表格。
5. **已印出的 QR 內容不可變。** 產生時把 QR 文字原樣存進資料庫，補印時用存下來的文字，不可重新組字串。
6. **報修網址用隨機代碼，不用序號。**
7. **不串接公司其他系統。** 現階段獨立運作，資料手動輸入。
8. **通知只用 Email。** 不要加簡訊、LINE、Telegram。
9. **客戶報修不需登入。**

## 工作方式

- **一次只做一個任務。** 依 `docs/06-phases.md` 的任務編號（例如 `P1-03`）進行，做完一個再做下一個。不要跳階段，不要順手做沒被要求的功能。
- **先讀再寫。** 動手前讀該任務列出的規格章節和相關現有程式。
- **做完要驗證。** 每個任務有驗收條件，要實際跑測試或啟動服務確認，不可只憑推測回報完成。跑不起來或沒驗證到的部分要明講。
- **規格沒寫或有矛盾時，停下來問。** 不要自行假設。小細節可以採用最保守的做法，並在回報中說明。
- **更新文件。** 實作與規格不同時（經使用者同意），同步修改對應的 `docs/` 檔案，並在 `docs/08-decisions.md` 加一筆。完成任務後在 `docs/06-phases.md` 把該任務打勾。
- **不要動的東西：** `vendor/qrcode.js` 與 `app/static/vendor/qrcode.js`（第三方函式庫，MIT）、根目錄 `index.html`（離線版）、`Claude outputs/` 資料夾（舊的輸出副本，忽略它）。

## 與使用者溝通

- 使用者用繁體中文，回覆一律用繁體中文、白話、先講結論。
- 使用者不熟悉 git。版本控制由 agent 代為處理，每次用一句白話說明做了什麼（例如「我把這次修改存成一個版本，之後可以還原」）。不要要求使用者自己下 git 指令。資料夾若還不是 git 版本庫，初始化前先問使用者。
- 不要一次丟一大串技術選項給使用者選。需要決定時給出建議做法和一句理由，再問是否同意。
- 回報完成時說明：做了什麼、怎麼驗證的、使用者要怎麼自己看到結果（例如開哪個網址）。

## 程式慣例

- 程式碼、識別字、commit 訊息用英文；介面文字、給使用者看的訊息用繁體中文。
- 日期一律 `YYYY-MM-DD`，時間存 UTC、顯示用 `Asia/Taipei`。
- 所有可調參數放 `settings` 資料表或環境變數，不寫死在程式裡。
- 不引入規格外的大型相依套件。要加新套件先說明原因。
- 詳細技術慣例見 `docs/02-architecture.md`。

## 常用指令

```bash
# 安裝（本機開發）
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt

# 啟動（需要 SECRET_KEY；資料庫沒有使用者時用 INITIAL_ADMIN_* 建立第一個負責人）
export SECRET_KEY=dev INITIAL_ADMIN_EMAIL=you@example.com INITIAL_ADMIN_PASSWORD=change-me-123
uvicorn app.asgi:app --reload --port 8000

# 測試
pytest                 # 單元與路由，約 15 秒
pytest tests/e2e       # 端對端（需 playwright + chromium、opencv、pypdf；沒裝會自動略過）

# 改了 app/models.py 之後產生資料庫遷移（啟動時會自動套用）
DATA_DIR=/tmp/mig SECRET_KEY=x alembic revision --autogenerate -m "說明"

# Docker 部署
cp .env.example .env && docker compose up -d --build     # http://<主機>:8088
```

注意：

- SQLite 需要建立與刪除暫存檔。若工作資料夾不允許刪除檔案，把 `DATA_DIR` 指到別處（例如 `/tmp/shipqr-data`）。
- 後台每個 POST 表單都要帶 `csrf_token` 隱藏欄位，路由要掛 `Depends(verify_csrf)`。
- 頁面上方導覽列有登出按鈕。端對端測試選取送出按鈕時用 `main button[type=submit]`，否則會點到登出。
