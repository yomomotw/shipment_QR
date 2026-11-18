# 05 路由

權限欄：公＝不需登入；客＝客服；負＝負責人；工＝工程師。負責人擁有客服的全部權限。

## 公開頁

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/d/{scan_code}` | 設備頁：型號、序號、保固狀態、勾選公開的資料、撥號按鈕。有未結案工單時顯示其進度；否則顯示報修表單（第二階段起）。已登入的內部人員導向 `/devices/{id}` | 公 |
| POST | `/d/{scan_code}/report` | 送出報修。成功後導向 `/t/{public_token}` | 公 |
| GET | `/t/{public_token}` | 進度查詢：工單編號、狀態、公開的事件、約定到場時間 | 公 |
| POST | `/t/{public_token}/quote` | 客戶同意或拒絕報價 | 公 |

公開頁的規則：

- 查不到的 `scan_code` 或 `public_token` 一律回 404 與相同的頁面。
- 設備頁可公開的欄位：型號、序號、保固狀態，以及 `device.qr_fields` 勾選的欄位。其他欄位（客戶名稱、未勾選的訂單號、維修內部備註）不可出現在頁面或頁面原始碼中。
- 回應加上 `X-Robots-Tag: noindex`。

## 登入

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET/POST | `/login` | 登入 |
| POST | `/logout` | 登出 |

未登入存取後台路徑時導向 `/login`，登入後回到原本要去的頁面。

## 設備與標籤

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/` | 導向 `/tickets`（負、工）或 `/devices`（客） | 登入 |
| GET | `/devices` | 台帳列表，可搜尋序號、訂單號、客戶名稱 | 客 |
| GET | `/devices/new` | 建檔表單 | 客 |
| POST | `/devices/preview` | 驗證輸入，回傳每台的 QR 文字與密度檢查結果，不寫入資料庫 | 客 |
| POST | `/devices` | 建立一批設備。任何一台驗證失敗就整批不建立 | 客 |
| GET | `/batches/{id}` | 該批標籤的列印頁（選尺寸、版面、列印、下載 ZIP／CSV） | 客 |
| GET | `/devices/{id}` | 設備詳情：資料、QR、工單履歷 | 客、工 |
| POST | `/devices/{id}` | 修改設備資料（不改 `qr_payload`、`scan_code`、`serial`） | 客 |
| POST | `/devices/{id}/regenerate-qr` | 重新產生 QR 文字，需二次確認 | 負 |
| GET | `/devices/{id}/label` | 單台補印 | 客 |

## 工單

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/tickets` | 工單列表，可依狀態、指派對象、日期篩選。工程師只看到指派給自己的 | 登入 |
| GET | `/tickets/new` | 手動建單（輸入序號帶出設備） | 客 |
| POST | `/tickets` | 建立工單（來源 = phone） | 客 |
| GET | `/tickets/{id}` | 工單詳情與事件紀錄 | 登入（工程師限自己的） |
| POST | `/tickets/{id}/transition` | 狀態轉換。規則見 `03-data-model.md` | 依轉換表 |
| POST | `/tickets/{id}/assign` | 指派工程師與約定時間 | 負 |
| POST | `/tickets/{id}/quote` | 填寫報價金額、記錄客戶回覆 | 負 |
| POST | `/tickets/{id}/notes` | 新增備註或附件，可標記是否公開 | 登入 |
| POST | `/tickets/{id}/complete` | 完修紀錄與客戶簽名 | 負、工 |
| GET | `/uploads/{path}` | 附件。工單附件需登入；不對外公開 | 登入 |

## 報表

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET | `/reports` | 四張報表（FR-50 ~ FR-53），可選日期區間，可下載 CSV | 負 |

## 管理

| 方法 | 路徑 | 說明 | 權限 |
|---|---|---|---|
| GET/POST | `/admin/settings` | 系統設定。修改已有值的 `public_base_url` 需確認警告 | 負 |
| POST | `/admin/settings/test-email` | 寄測試信 | 負 |
| GET/POST | `/admin/users` | 使用者管理 | 負 |
| GET | `/admin/notifications` | 通知紀錄，可篩選失敗的 | 負 |
| GET/POST | `/admin/faq` | 常見問題維護（第四階段） | 負 |

## 其他

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET | `/healthz` | 健康檢查，回 200 |
