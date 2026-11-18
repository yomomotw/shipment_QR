# 出貨標籤 QR 與設備叫修系統

每台設備一張小標籤（QR ＋ 序號、型號、叫修電話）。QR 內含離線可讀的基本資料，設定對外網址後多帶一行線上報修網址。

目前完成第一階段：登入、系統設定、設備建檔、標籤列印、設備台帳、公開設備頁。工單與線上報修在第二階段。進度見 `docs/06-phases.md`。

## 啟動

### Docker（建議）

```bash
cp .env.example .env      # 然後編輯 .env，填入 SECRET_KEY 與第一個負責人帳號
docker compose up -d --build
# 開啟 http://<主機IP>:8088 ，用 .env 裡的帳號登入
```

資料都在 `data/` 資料夾（資料庫 `app.db`）。備份 = 複製整個 `data/`。

### 本機開發

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export SECRET_KEY=dev INITIAL_ADMIN_EMAIL=you@example.com INITIAL_ADMIN_PASSWORD=change-me-123
uvicorn app.asgi:app --reload --port 8000
```

## 第一次使用

1. 登入後到「系統設定」填叫修電話（必填）。對外網址可以先留空。
2. 「建檔與印標籤」：填型號、規格、訂單、序號，勾選要寫進 QR 的資料，按「檢查並預覽」，再按「建立並前往列印」。
3. 列印頁選版面與尺寸，按「列印 / 存成 PDF」。

## 測試

```bash
pytest                      # 單元與路由測試
# 端對端測試（真的開瀏覽器、解碼 QR 比對），需要額外安裝：
pip install playwright opencv-python-headless pypdf && playwright install chromium
pytest tests/e2e
```

## 離線版

根目錄的 `index.html` 是最早的純前端版，直接用瀏覽器開啟就能產生標籤，不需要伺服器。它**不會**把設備存進台帳，QR 格式也是舊版，只適合臨時使用。

## 文件

給 AI 開發用的規格在 `AGENTS.md` 與 `docs/`。

## 第三方元件

- `app/static/vendor/qrcode.js` — [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) 1.4.4（MIT）
