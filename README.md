# W11 作業：股票 LINE Bot

> **繳交方式**：將你的 GitHub repo 網址貼到作業繳交區
> **作業性質**：個人作業

---

## 作業目標

利用上週設計的 Skill，開發一個股票相關的 LINE Bot。
重點不是功能多寡，而是你設計的 **Skill 品質**——Skill 寫得越具體，AI 產出的程式碼就越接近可以直接執行。

---

## 功能要求（擇一實作）

| 功能 | 說明 |
| --- | --- |
| AI 分析股票 | 使用者說股票名稱，Gemini 給出分析 |
| 追蹤清單 | 儲存使用者的自選股清單到 SQLite |
| 查詢即時價格 | 整合 yfinance 或 twstock 取得股價 |

> 以「可以執行、能回覆訊息」為目標，不需要複雜

---

## 繳交項目

你的 GitHub repo 需要包含：

| 項目 | 說明 |
| --- | --- |
| `app.py` | LINE Webhook + Gemini + SQLite 後端 |
| `requirements.txt` | 所有套件 |
| `.env.example` | 環境變數範本（不含真實 token） |
| `.agents/skills/` | 至少包含 `/linebot-implement` Skill |
| `README.md` | 本檔案（含心得報告） |
| `screenshots/chat.png` | LINE Bot 對話截圖（至少一輪完整對話） |

### Skill 要求

`.agents/skills/` 至少需要包含：

- `/linebot-implement`：產出 LINE Bot 主程式（必要）
- `/prd` 或 `/architecture`：延用上週的
- `/commit`：延用上週的

---

## 專案結構

```
your-repo/
├── .agents/
│   └── skills/
│       ├── prd/SKILL.md
│       ├── linebot-implement/SKILL.md
│       └── commit/SKILL.md
├── docs/
│   └── PRD.md
├── screenshots/
│   └── chat.png
├── app.py
├── requirements.txt
├── .env.example
└── README.md
```

> `.env` 和 `users.db` 不要 commit（加入 `.gitignore`）

---

## 啟動方式

```bash
# 1. 建立虛擬環境
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. 安裝套件
pip install -r requirements.txt

# 3. 設定環境變數
cp .env.example .env
# 編輯 .env，填入三個 token

# 4. 啟動 FastAPI
uvicorn app:app --reload

# 5. 另開終端機啟動 ngrok
ngrok http 8000
# 複製 https 網址，填入 LINE Developers Console 的 Webhook URL（加上 /callback）
# 點「Verify」確認連線正常後，掃 QR Code 加好友開始測試
```

---

## 心得報告

**姓名**：林伽紜
**學號**：D1149890

**Q1. 你在 `/linebot-implement` Skill 的「注意事項」寫了哪些規則？為什麼這樣寫？**

> **規則 1：強制使用 line-bot-sdk-python v3 版本**
> - *原因：* 避免 AI 使用舊版的 v2 語法，因為新舊版在模組匯入與訊息傳送邏輯上有巨大差異。
>
> **規則 2：金鑰必須透過 .env 讀取，嚴禁寫死在程式碼中**
> - *原因：* 為了保護 Channel Secret 等機密不被誤傳至 GitHub，這也是資安的基本規範。

---

**Q2. 你的 Skill 第一次執行後，AI 產出的程式直接能跑嗎？需要修改哪些地方？修改後有沒有更新 Skill？**

*   **執行狀況：** 無法直接執行，需要手動介入。
*   **修改地方：**
    1. 需手動將 `gemini-pro` 改為 `gemini-3.1-flash-lite-preview` 才能正常運作。
    2. 必須手動在 LINE Console 設定 Webhook URL 並補上 `/callback`。
*   **更新 Skill：** 是的，我已將 Gemini 的正確模型名稱寫入 Skill 限制中，避免 AI 下次再調用舊模型。
---

**Q3. 你遇到什麼問題是 AI 沒辦法自己解決、需要你介入處理的？**

1.  **環境架構衝突：** 在 Mac 上安裝 ngrok 時遇到 bad CPU type 的架構不相容問題，需要我手動移除檔案並透過 Homebrew 重新安裝。
2.  **控制台手動設定：** LINE Developers Console 的 Use webhook 開關必須手動開啟，AI 無法進入網頁幫我操作。

---

**Q4. 如果你要把這個 LINE Bot 讓朋友使用，你還需要做什麼？**

*   **雲端部署：** 目前跑在本地電腦，若要讓朋友隨時使用，需要部署到 Render 或 Railway 等雲端平台。
*   **固定網址：** 目前使用 ngrok 每次開啟網址都會變動，需要申請一個固定的域名 (Domain)。
*   **流量控管：** 避免 Gemini API 被濫用，需要加入頻率限制或對話管理功能。
