# 📈 股票 LINE Bot — 產品需求規格書 (PRD)

## 文件資訊

| 項目 | 內容 |
|------|------|
| 專案名稱 | Stock AI LINE Bot（股票智慧助手） |
| 版本 | v1.0 |
| 建立日期 | 2026-05-05 |
| 狀態 | 草稿 (Draft) |

---

## 1. 產品概述

### 1.1 產品簡介

「股票智慧助手」是一個以 LINE 為介面的聊天機器人，使用者可以透過 LINE 傳送文字訊息查詢股票資訊、獲取 AI 分析建議。系統結合 Google Gemini API 提供智慧回覆，並使用 SQLite 資料庫記錄所有使用者互動歷程。

### 1.2 目標使用者

- 對股票有興趣的一般投資人
- 想快速查詢個股價格與基本面的 LINE 使用者
- 希望透過 AI 獲得股票分析觀點的入門投資者

### 1.3 產品目標

1. 提供便捷的 LINE 介面，讓使用者能即時查詢股票資訊
2. 運用 Gemini AI 產生有參考價值的股票分析內容
3. 完整記錄使用者互動資料，供後續分析與功能迭代

### 1.4 成功指標

| 指標 | 目標 |
|------|------|
| Bot 可正常回覆訊息 | 99% 以上的訊息能在 10 秒內回覆 |
| AI 回覆品質 | 回覆內容與股票查詢相關且有邏輯 |
| 資料記錄完整性 | 100% 的互動紀錄皆被寫入 SQLite |

---

## 2. 技術架構

### 2.1 系統架構圖

```
┌──────────┐     HTTPS      ┌──────────────┐     API      ┌─────────────┐
│  LINE    │ ──Webhook────▶ │ FastAPI App  │ ───────────▶ │ Gemini API  │
│  使用者   │ ◀─Reply──────  │  (Python)    │ ◀─────────── │ (Google AI) │
└──────────┘                └──────┬───────┘              └─────────────┘
                                   │
                                   │ Read/Write
                                   ▼
                            ┌──────────────┐
                            │   SQLite DB  │
                            │  (本地檔案)   │
                            └──────────────┘
```

### 2.2 技術選型

| 層級 | 技術 | 版本/說明 |
|------|------|----------|
| 語言 | Python | >= 3.10 |
| LINE SDK | line-bot-sdk-python | v3（使用 `linebot.v3` 模組） |
| Web 框架 | FastAPI + Uvicorn | 原生 async、自動 API 文件 |
| AI 引擎 | Google Gemini API | `google-genai` 套件 |
| 資料庫 | SQLite | 內建輕量資料庫，無需額外安裝 |
| 環境變數 | python-dotenv | 管理敏感設定 |
| 部署 | ngrok（開發）/ Cloud Run（正式） | HTTPS Webhook 端點 |

### 2.3 專案目錄結構

```
stock-line-bot/
├── .env                    # 環境變數（不進版控）
├── .gitignore
├── requirements.txt
├── docs/
│   ├── PRD.md              # 本文件
│   └── ARCHITECTURE.md     # 系統架構文件
├── app.py                  # 主程式：FastAPI + Webhook
├── line_handler.py         # LINE 事件處理器
├── gemini_service.py       # Gemini API 互動邏輯
├── config.py               # 環境變數集中管理
├── db.py                   # SQLite 資料庫操作
├── stock_data.db           # SQLite 資料庫檔案（自動產生）
└── README.md
```

---

## 3. 功能需求

### 3.1 核心功能（MVP）

#### F1：接收與回覆 LINE 訊息

| 項目 | 說明 |
|------|------|
| 描述 | Bot 接收使用者在 LINE 傳送的文字訊息，並回覆對應內容 |
| 觸發條件 | 使用者在 LINE 對話中傳送文字訊息 |
| 技術實作 | 使用 `line-bot-sdk-python v3` 的 `WebhookHandler` 處理 `MessageEvent` |
| 輸入 | 使用者文字訊息（如「台積電」「2330 股價」「分析 0050」） |
| 輸出 | AI 生成的股票分析回覆文字 |
| 錯誤處理 | 非文字訊息回覆提示「目前僅支援文字查詢」 |

**Webhook 處理流程：**

```
1. LINE Platform 發送 Webhook POST 到 /callback
2. 驗證 X-Line-Signature
3. 解析 MessageEvent + TextMessageContent
4. 擷取使用者訊息文字與 userId
5. 將使用者訊息送往 Gemini API
6. 將 AI 回覆透過 reply_message 回傳
7. 將互動紀錄寫入 SQLite
```

#### F2：Gemini AI 股票分析

| 項目 | 說明 |
|------|------|
| 描述 | 將使用者輸入送至 Gemini API，以股票分析助手的角色產生回覆 |
| AI 模型 | Gemini 2.0 Flash（或可用版本） |
| System Prompt | 設定為「你是一位專業的股票分析助手，提供台灣與美國股市的資訊查詢與分析」 |
| 回覆限制 | 單次回覆不超過 2000 字元（LINE 文字訊息上限 5000 字元） |
| 免責聲明 | 每次 AI 回覆結尾自動附加「⚠️ 以上為 AI 分析，不構成投資建議」 |

**System Prompt 設計：**

```
你是一位專業的台灣股票分析助手。
- 回覆使用繁體中文
- 若使用者詢問特定股票，提供公司簡介、近期趨勢分析、產業展望
- 若使用者輸入股票代號（如 2330），識別為台灣上市股票代號
- 回覆簡潔明瞭，適合在手機上閱讀
- 結尾加上免責聲明
- 若無法判斷股票相關意圖，友善引導使用者提供更明確的查詢
```

#### F3：SQLite 使用者互動紀錄

| 項目 | 說明 |
|------|------|
| 描述 | 記錄每一筆使用者與 Bot 的互動，包含使用者 ID、輸入訊息、AI 回覆、時間戳 |
| 資料庫 | SQLite（檔案：`stock_data.db`） |
| 自動建表 | 程式啟動時自動檢查並建立所需表格 |

**資料表設計：**

##### `users` 表

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | 自增主鍵 |
| user_id | TEXT UNIQUE NOT NULL | LINE userId |
| display_name | TEXT | 使用者顯示名稱（可選） |
| created_at | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | 首次互動時間 |
| last_active_at | TIMESTAMP | 最後互動時間 |

##### `chat_history` 表

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | 自增主鍵 |
| user_id | TEXT NOT NULL | LINE userId（外鍵關聯 users） |
| user_message | TEXT NOT NULL | 使用者輸入的訊息 |
| bot_reply | TEXT NOT NULL | Bot 回覆的訊息 |
| created_at | TIMESTAMP DEFAULT CURRENT_TIMESTAMP | 訊息時間 |

**建表 SQL：**

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE NOT NULL,
    display_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    user_message TEXT NOT NULL,
    bot_reply TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
```

---

### 3.2 使用者互動流程

```
使用者加入好友
    │
    ▼
Bot 發送歡迎訊息：
「👋 歡迎使用股票智慧助手！
  輸入股票名稱或代號即可查詢，例如：
  ・台積電
  ・2330
  ・分析 0050」
    │
    ▼
使用者傳送文字訊息
    │
    ├─ 文字訊息 → Gemini AI 分析 → 回覆結果 → 儲存紀錄
    │
    └─ 非文字訊息 → 回覆「目前僅支援文字查詢喔 📝」
```

### 3.3 事件處理對照表

| 事件 | 處理方式 |
|------|---------|
| `FollowEvent`（加好友） | 回覆歡迎訊息，新增使用者至 `users` 表 |
| `MessageEvent` + `TextMessageContent` | 呼叫 Gemini API → 回覆 → 寫入 `chat_history` |
| `MessageEvent` + 非文字 | 回覆「目前僅支援文字查詢」 |
| `UnfollowEvent`（封鎖） | 記錄 log，不刪除使用者資料 |
| 其他事件 | 忽略（不處理） |

---

## 4. 非功能需求

### 4.1 效能

- Webhook 回應時間 < 1 秒（先回覆再背景處理 AI）
- Gemini API 回覆超過 10 秒時，先以「分析中，請稍候…」回覆使用者
- 耗時操作使用背景執行緒，避免 Webhook timeout

### 4.2 安全性

- 所有敏感資訊（Token、API Key）透過環境變數管理，**禁止寫死在程式碼中**
- `.env` 檔案必須加入 `.gitignore`
- Webhook 端點驗證 `X-Line-Signature` 防止偽造請求
- AI 回覆加上免責聲明，避免法律風險

### 4.3 可靠性

- 使用 `delivery_context.is_redelivery` 判斷重複 Webhook 避免重複處理
- Gemini API 呼叫失敗時回覆「系統忙碌中，請稍後再試」
- SQLite 寫入失敗時記錄 error log，不影響使用者回覆

### 4.4 可維護性

- 程式碼依職責分離：`app.py`（路由）、`gemini_service.py`（AI）、`db.py`（資料庫）
- 使用 Python logging 模組記錄關鍵操作
- README.md 包含完整的設定與啟動說明

---

## 5. 環境變數清單

| 變數名稱 | 說明 | 範例 |
|---------|------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Bot Channel Access Token | `xxxxxxxx` |
| `LINE_CHANNEL_SECRET` | LINE Bot Channel Secret | `xxxxxxxx` |
| `GEMINI_API_KEY` | Google Gemini API Key | `AIzaSy...` |

`.env` 範例：

```env
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
LINE_CHANNEL_SECRET=your_channel_secret
GEMINI_API_KEY=your_gemini_api_key
```

---

## 6. 依賴套件

```txt
fastapi
uvicorn[standard]
line-bot-sdk
google-genai
python-dotenv
aiosqlite
```

安裝指令：

```bash
pip install fastapi uvicorn[standard] line-bot-sdk google-genai python-dotenv aiosqlite
```

---

## 7. API 規格

### 7.1 Webhook 端點

| 項目 | 說明 |
|------|------|
| Method | POST |
| Path | `/callback` |
| Headers | `X-Line-Signature`（LINE Platform 提供） |
| Body | JSON（LINE Webhook Event） |
| Response | `200 OK`，Body：`"OK"` |

### 7.2 外部 API 呼叫

| API | 用途 | 呼叫時機 |
|-----|------|---------|
| LINE Messaging API — `reply_message` | 回覆使用者訊息 | 收到 Webhook 事件時 |
| LINE Messaging API — `push_message` | 主動推送（背景處理完成後） | AI 回覆耗時超過閾值時 |
| Google Gemini API — `generate_content` | 產生股票分析文字 | 收到使用者文字訊息時 |

---

## 8. 開發里程碑

### Phase 1：基礎架構（Week 1）

- [ ] 建立專案結構與 Git repo
- [ ] 設定環境變數與 `.env`
- [ ] 實作 FastAPI Webhook（`app.py`）
- [ ] 實作 Echo Bot（收到什麼回什麼）
- [ ] 使用 ngrok 測試 Webhook 連線

### Phase 2：AI 整合（Week 2）

- [ ] 實作 `gemini_service.py`（Gemini API 呼叫）
- [ ] 設計 System Prompt
- [ ] 串接 AI 回覆至 LINE Bot
- [ ] 處理 AI 回覆超時的 fallback 機制

### Phase 3：資料庫（Week 3）

- [ ] 實作 `db.py`（SQLite CRUD）
- [ ] 自動建表邏輯
- [ ] 每次互動自動寫入 `chat_history`
- [ ] 新使用者自動建立 `users` 紀錄

### Phase 4：完善與測試（Week 4）

- [ ] 加入 FollowEvent 歡迎訊息
- [ ] 非文字訊息的錯誤處理
- [ ] 加入免責聲明
- [ ] 完整測試所有流程
- [ ] 撰寫 README.md

---

## 9. 風險與限制

| 風險 | 影響 | 緩解措施 |
|------|------|---------|
| Gemini API 回覆速度不穩定 | 使用者等待過久 | 先回覆「處理中」，AI 結果用 push_message |
| Reply Token 30 秒過期 | 無法回覆 | 確保先 reply 再做耗時操作 |
| Gemini 免費額度用盡 | Bot 無法產生 AI 回覆 | 設定 fallback 訊息、監控用量 |
| AI 產生不當投資建議 | 法律風險 | 強制加上免責聲明 |
| SQLite 並發寫入衝突 | 資料遺失 | 使用 `threading.Lock` 或 WAL 模式 |

---

## 10. 未來擴展（Post-MVP）

- 🔌 串接即時股價 API（如 FinMind、Yahoo Finance）取得真實報價
- 📊 支援回覆 Flex Message 呈現股票卡片（含漲跌、成交量）
- 🔔 自選股提醒功能（價格到達通知）
- 📜 使用者可查詢自己的歷史查詢紀錄
- 🌐 部署至 Google Cloud Run 正式上線
- 📱 Rich Menu 快捷選單（熱門股票、使用說明）
