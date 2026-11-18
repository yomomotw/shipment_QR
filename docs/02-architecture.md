# 02 架構

## 技術選型

| 項目 | 選擇 | 理由 |
|---|---|---|
| 後端 | Python 3.12 + FastAPI | 單一服務就能提供頁面與 API，部署簡單 |
| 資料庫 | SQLite（單一檔案） | 使用量小、自架、備份只要複製一個檔 |
| ORM／遷移 | SQLAlchemy 2 + Alembic | 資料表會隨階段增加，需要可追蹤的結構變更 |
| 頁面 | 伺服器端 Jinja2 模板 + 原生 JavaScript | 不需要前端建置流程；沿用現有 `index.html` 的寫法 |
| QR 產生 | 瀏覽器端 `vendor/qrcode.js`（qrcode-generator 1.4.4） | 現有程式已驗證可正確編碼中文；QR 文字由後端產生並保存 |
| 登入 | Email + 密碼（argon2），簽章的 session cookie，有效 12 小時 | 內部使用者少，不需要第三方登入 |
| 寄信 | SMTP（設定存資料庫） | 只用 Email 通知 |
| 測試 | pytest + httpx；QR 與頁面用 Playwright | 見 `07-testing.md` |
| 部署 | Docker Compose，單一容器 | 目標環境是自架主機／NAS |

這份選型是設計階段的建議，尚未經使用者逐項確認（見 `08-decisions.md` A-01）。要更換其中任何一項，先問使用者。

## 目錄結構

```
shipment_QR/
├── AGENTS.md  CLAUDE.md  README.md
├── docs/                    規格文件
├── app/
│   ├── main.py              FastAPI 進入點
│   ├── config.py            環境變數
│   ├── db.py                資料庫連線
│   ├── models.py            SQLAlchemy 資料表
│   ├── services/
│   │   ├── serials.py       序號解析（範圍展開、重複檢查）
│   │   ├── qr_payload.py    QR 文字組裝（唯一來源）
│   │   ├── warranty.py      保固到期日與在保判斷
│   │   ├── tickets.py       工單狀態機
│   │   ├── mailer.py        寄信
│   │   └── auth.py          登入、權限
│   ├── routers/
│   │   ├── public.py        /d/{code}、/t/{token}
│   │   ├── devices.py       台帳、標籤
│   │   ├── tickets.py       工單
│   │   ├── reports.py
│   │   └── admin.py         設定、使用者
│   ├── templates/           Jinja2 模板
│   └── static/
│       ├── vendor/qrcode.js
│       ├── label.js         標籤排版與 QR 繪製（由現有 index.html 拆出）
│       └── style.css
├── migrations/              Alembic
├── tests/
├── data/                    執行期資料（不進版本控制）
│   ├── app.db
│   └── uploads/
├── Dockerfile
└── docker-compose.yml
```

現有的 `index.html` 在 P1 拆進 `app/templates/` 與 `app/static/label.js`。拆完後根目錄的 `index.html` 保留為離線版，並在 README 註明它不會寫入台帳。

## 關鍵設計

### QR 文字只有一個產生來源

`app/services/qr_payload.py` 是唯一組裝 QR 文字的地方。建立設備時呼叫一次，結果存進 `device.qr_payload`。之後所有顯示、補印、下載都讀這個欄位，不重新組裝。瀏覽器端的 `label.js` 只負責把收到的文字畫成 QR，不自行組字串。

### 公開頁與後台分離

- 公開頁：`/d/{scan_code}`（設備頁與報修）、`/t/{public_token}`（進度查詢）。不需登入，只能看到規格允許公開的欄位。
- 後台：其餘全部需要登入。
- 部署時可以只把 `/d/`、`/t/`、`/static/` 對外開放，後台留在內網。程式要支援這種反向代理設定，不可假設所有路徑都在同一個對外網域。

### 工單狀態機集中管理

狀態轉換只能透過 `app/services/tickets.py` 的函式進行。路由不可直接改 `ticket.status`。每次轉換同時寫入一筆 `ticket_event`。

### 寄信不阻擋操作

寄信放在請求完成後的背景工作。失敗時寫入 `notification_log`，不讓使用者的操作失敗。

## 安全要求

- 密碼用 argon2 或 bcrypt 雜湊，不可明文或可逆加密。
- Session cookie 設 `HttpOnly`、`SameSite=Lax`，在 HTTPS 下設 `Secure`。
- 所有會改資料的表單要有 CSRF 防護（公開報修表單也要）。
- 模板輸出一律跳脫。客戶填的問題描述、規格文字都是不可信輸入。
- 上傳檔案：限制類型（jpg、png、heic、mp4、mov）、單檔 20 MB、每張工單 5 個。存檔用隨機檔名，不用客戶提供的檔名。上傳目錄不可被當成程式執行。
- 公開頁查不到的代碼一律回同一個「找不到」頁面，不透露代碼是否曾存在。
- 報修頻率限制：同一設備每小時 3 次，同一 IP 每小時 10 次（數值放設定，可調）。
- SMTP 密碼存資料庫時，設定頁不回顯明文。
- 不在日誌裡記錄密碼、session、SMTP 密碼。

## 環境變數

| 變數 | 用途 | 預設 |
|---|---|---|
| `DATA_DIR` | 資料庫與上傳檔位置 | `./data` |
| `SECRET_KEY` | session 簽章 | 無，必填 |
| `INITIAL_ADMIN_EMAIL` / `INITIAL_ADMIN_PASSWORD` | 第一次啟動時建立負責人帳號 | 無 |
| `TZ` | 顯示時區 | `Asia/Taipei` |
| `HTTPS_ONLY` | 設為 `1` 時 session cookie 加上 `Secure` | `0` |

其餘可調參數（對外網址、叫修電話、SMTP 等）放資料庫的 `settings`，由設定頁修改。

## 部署

- 先 `cp .env.example .env` 並填值，再 `docker compose up -d --build` 啟動，對外埠 8088。
- 程式進入點是 `app/asgi.py`（`uvicorn app.asgi:app`），`app/main.py` 的 `create_app()` 負責組裝。
- `data/` 掛成 volume。備份 = 複製整個 `data/` 資料夾。
- 啟動時自動執行資料庫遷移。
