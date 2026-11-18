# 03 資料模型

所有資料表都有 `id`（整數主鍵）、`created_at`、`updated_at`（UTC）。以下只列業務欄位。

## device 設備

一筆代表一台出貨的設備。

| 欄位 | 型別 | 說明 |
|---|---|---|
| serial | 文字，唯一 | 序號 |
| scan_code | 文字，唯一 | 報修網址用的隨機代碼。產生規則見 `04-qr-label-spec.md` |
| model | 文字 | 型號 |
| spec | 多行文字 | 規格，可空 |
| ship_date | 日期 | 出貨日期 |
| cust_po | 文字 | 客戶訂單編號 |
| int_po | 文字 | 內部訂單編號 |
| customer_name | 文字 | 客戶名稱，可空 |
| warranty_months | 整數 | 保固長度（月） |
| warranty_start | 日期 | 保固開始日，預設 = ship_date，可手動改 |
| warranty_end | 日期 | = warranty_start + warranty_months。存欄位，前兩者任一變更時重算 |
| service_tel | 文字 | 建檔當下的叫修電話。印在標籤上並寫進 QR，建檔後不隨系統設定改變，補印才會與 QR 一致 |
| note | 多行文字 | 備註。重新產生 QR 時系統會加一行紀錄 |
| external_ref | 文字，可空 | 保留給日後串接 |
| qr_fields | JSON 陣列 | 建檔時勾選寫進 QR 的欄位，值為 `spec`、`ship_date`、`cust_po`、`int_po`、`warranty` 的子集合 |
| qr_payload | 多行文字 | 產生當下的 QR 完整文字。**寫入後不可修改** |
| batch_id | 外鍵 → batch | 同一次建立的設備屬同一批 |

規則：

- `qr_payload` 一旦寫入就不更新。之後修改型號、規格等欄位，只改資料庫，不改 `qr_payload`。設備詳情頁在兩者不一致時顯示提示「標籤上的 QR 是舊資料，需要的話請重新產生並換貼」。
- 「重新產生 QR」是明確的操作：用目前資料與目前的叫修電話產生新的 `qr_payload`（`scan_code` 不變），並在設備上記一筆備註。只有負責人可以做。

## batch 批次

一次建檔操作。用來把同批設備一起列印、下載。

| 欄位 | 說明 |
|---|---|
| created_by | 外鍵 → user |
| label_size | 當時選的標籤尺寸，例如 `60x40` |
| note | 備註，可空 |

## ticket 工單

一筆代表一次報修。

| 欄位 | 型別 | 說明 |
|---|---|---|
| ticket_no | 文字，唯一 | 格式 `T` + `YYMMDD` + `-` + 三位流水號，例如 `T261117-001`。流水號每日重新起算 |
| public_token | 文字，唯一 | 進度查詢網址用的隨機字串（至少 16 字元） |
| device_id | 外鍵 → device | |
| source | `scan` / `phone` | 來源 |
| contact_name / contact_phone / contact_email | 文字 | 聯絡資料 |
| description | 多行文字 | 問題描述 |
| status | 見下方狀態 | |
| in_warranty | 布林 | 建單當下依 `device.warranty_end` 判定，之後不變 |
| quote_status | `none` / `pending` / `approved` / `declined` | 在保的工單為 `none` |
| quote_amount | 整數，可空 | 報價金額（新台幣） |
| assignee_id | 外鍵 → user，可空 | 指派的工程師 |
| scheduled_at | 時間，可空 | 約定到場時間 |
| fault_cause / resolution / parts_replaced | 文字，可空 | 完修紀錄 |
| signature_path | 文字，可空 | 客戶簽名圖檔 |
| accepted_at / completed_at / closed_at | 時間，可空 | 供報表計算 |

## 工單狀態機

| 狀態 | 代碼 |
|---|---|
| 待處理 | `new` |
| 已受理 | `accepted` |
| 處理中 | `in_progress` |
| 待料 | `waiting_parts` |
| 已完修 | `completed` |
| 已結案 | `closed` |
| 已取消 | `cancelled` |

允許的轉換：

| 從 | 到 | 誰可以 | 條件 |
|---|---|---|---|
| new | accepted | 負責人 | — |
| accepted | in_progress | 負責人、被指派的工程師 | 已指派工程師；且 `quote_status` 為 `none` 或 `approved` |
| in_progress | waiting_parts | 負責人、被指派的工程師 | — |
| waiting_parts | in_progress | 負責人、被指派的工程師 | — |
| in_progress | completed | 負責人、被指派的工程師 | 已填故障原因與處理方式 |
| completed | closed | 負責人 | — |
| completed | in_progress | 負責人 | 客戶反映沒修好，需附備註 |
| new、accepted、in_progress、waiting_parts | cancelled | 負責人 | 需附原因 |

其他轉換一律拒絕。`closed`、`cancelled` 是終點。

受理（new → accepted）時，若 `in_warranty` 為否，`quote_status` 自動設為 `pending`。報價被拒（`declined`）時，負責人把工單取消。

「未結案工單」指狀態不是 `closed`、`cancelled` 的工單。同一台設備同時最多一張未結案工單（FR-24）。電話建單遇到已有未結案工單時，提示並導向該工單。

## ticket_event 工單事件

工單上的每一次動作。只新增，不修改、不刪除。

| 欄位 | 說明 |
|---|---|
| ticket_id | 外鍵 |
| actor_id | 外鍵 → user；客戶的動作為空 |
| type | `status_change` / `note` / `attachment` / `assign` / `quote` / `notify` |
| from_status / to_status | 狀態變更時填 |
| body | 文字內容 |
| is_public | 布林。為真時顯示在客戶的進度查詢頁 |

## attachment 附件

| 欄位 | 說明 |
|---|---|
| ticket_id | 外鍵 |
| event_id | 外鍵 → ticket_event |
| path | 存放路徑（隨機檔名） |
| mime / size | 類型與大小 |
| uploaded_by | 外鍵 → user；客戶上傳為空 |

## user 內部使用者

| 欄位 | 說明 |
|---|---|
| email | 唯一，登入帳號，也是通知收件地址 |
| name | 顯示名稱 |
| password_hash | |
| role | `manager`（負責人）/ `agent`（客服）/ `engineer`（工程師） |
| is_active | 停用後不可登入，歷史紀錄保留 |

## settings 設定

鍵值表。鍵如下：

| 鍵 | 說明 | 預設 |
|---|---|---|
| public_base_url | 對外網址，例如 `https://service.example.com`。可空 | 空 |
| service_tel | 叫修電話 | 空（建檔前必須先設定） |
| default_warranty_months | 預設保固月數 | 12 |
| smtp_host / smtp_port / smtp_user / smtp_password / smtp_from | 寄信設定 | 空 |
| notify_emails | 新工單通知的額外收件人，逗號分隔 | 空 |
| unaccepted_reminder_hours | 未受理提醒時數 | 4 |
| rate_limit_per_device_hour / rate_limit_per_ip_hour | 報修頻率上限 | 3 / 10 |

預設保固 12 個月、提醒 4 小時是暫定值，使用者未指定，可在設定頁修改。

## notification_log 通知紀錄

| 欄位 | 說明 |
|---|---|
| ticket_id | 外鍵，可空 |
| to_email / subject | |
| status | `sent` / `failed` |
| error | 失敗原因 |

## faq 常見問題（第四階段）

| 欄位 | 說明 |
|---|---|
| model | 型號（與 device.model 字串比對） |
| question / answer | |
| sort | 排序 |

## 為日後串接保留的空間

現階段不串接公司系統。只需做到兩點，不要多做：

- `device` 與 `ticket` 各留一個可空的 `external_ref` 文字欄位。
- 建立設備的邏輯寫成服務函式（`services/`），不寫死在路由裡，日後匯入功能可以重用。
