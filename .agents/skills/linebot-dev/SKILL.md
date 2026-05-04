# LINE Bot 開發指南 (line-bot-sdk-python v3)

## 適用情境

當使用者要求開發 LINE Bot 時，依照本指南使用 `line-bot-sdk-python` **v3** 版本撰寫程式碼。

> **⚠️ Gemini 模型選用規則：** 所有使用 Gemini API 的場景，預設優先使用 `gemini-3.1-flash-lite-preview` 模型，除非使用者明確指定其他模型。

---

## 1. 開發前 Checklist

- [ ] 已在 [LINE Developers Console](https://developers.line.biz/console/) 建立 Provider 與 Messaging API Channel
- [ ] 已取得 **Channel Secret** 與 **Channel Access Token (long-lived)**
- [ ] 環境變數已設定（`LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN`）
- [ ] 已安裝 SDK：`pip install line-bot-sdk flask python-dotenv`
- [ ] Python 版本 >= 3.10
- [ ] Webhook URL 已設定且為 HTTPS（可用 ngrok 開發測試）
- [ ] 已開啟「Use webhook」、關閉「Auto-reply messages」

---

## 2. v2 vs v3 差異對照表

| 項目 | v2 (`linebot`) | v3 (`linebot.v3`) |
|------|----------------|---------------------|
| 匯入路徑 | `from linebot import LineBotApi, WebhookHandler` | `from linebot.v3 import WebhookHandler`<br>`from linebot.v3.messaging import MessagingApi, Configuration, ApiClient` |
| 初始化 API | `LineBotApi(token)` | `Configuration(access_token=token)` + `ApiClient` + `MessagingApi` |
| 回覆訊息 | `line_bot_api.reply_message(token, TextSendMessage(text=...))` | `MessagingApi(client).reply_message(ReplyMessageRequest(reply_token=..., messages=[TextMessage(text=...)]))` |
| 訊息物件 | `TextSendMessage`, `ImageSendMessage` | `TextMessage`, `ImageMessage` |
| Webhook 事件 | `from linebot.models import MessageEvent, TextMessage` | `from linebot.v3.webhooks import MessageEvent, TextMessageContent` |
| 訊息 filter | `@handler.add(MessageEvent, message=TextMessage)` | `@handler.add(MessageEvent, message=TextMessageContent)` |
| 例外處理 | `from linebot.exceptions import InvalidSignatureError` | `from linebot.v3.exceptions import InvalidSignatureError` |
| 程式碼生成 | 手動維護 | 基於 OpenAPI spec 自動生成 |

> **重要：v2 模組 (`linebot`) 已停止更新，所有新專案必須使用 `linebot.v3`。**

---

## 3. Webhook + Handler 標準寫法（Flask）

```python
import os
from flask import Flask, request, abort
from dotenv import load_dotenv

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
)

load_dotenv()

app = Flask(__name__)

# ✅ 從環境變數讀取，絕對不要寫死
configuration = Configuration(access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["LINE_CHANNEL_SECRET"])


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature.")
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=event.message.text)],
            )
        )


if __name__ == "__main__":
    app.run(port=5000)
```

### FastAPI 版本

```python
import os
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

load_dotenv()

app = FastAPI()
configuration = Configuration(access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["LINE_CHANNEL_SECRET"])


@app.post("/callback")
async def callback(request: Request):
    signature = request.headers["X-Line-Signature"]
    body = (await request.body()).decode("utf-8")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=event.message.text)],
            )
        )
```

---

## 4. 常見地雷 🚨

### 4.1 Reply Token 限制

- Reply token **只能使用一次**，且必須在收到 webhook 後 **30 秒內** 使用
- 一次 reply 最多 **5 則訊息**
- 若需多次主動推送，改用 `push_message`（有費用）

```python
# ❌ 錯誤：reply token 用了兩次
line_bot_api.reply_message(...)  # 第一次 OK
line_bot_api.reply_message(...)  # 第二次會失敗

# ✅ 正確：一次送多則訊息
line_bot_api.reply_message_with_http_info(
    ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[
            TextMessage(text="訊息 1"),
            TextMessage(text="訊息 2"),
        ],
    )
)

# ✅ 需要額外推送時用 push_message
from linebot.v3.messaging import PushMessageRequest

line_bot_api.push_message(
    PushMessageRequest(
        to=event.source.user_id,
        messages=[TextMessage(text="主動推送")],
    )
)
```

### 4.2 環境變數不能寫死

```python
# ❌ 絕對不要這樣做
configuration = Configuration(access_token="YOUR_REAL_TOKEN_HERE")

# ✅ 使用環境變數
configuration = Configuration(access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"])

# ✅ 加上 .env 檔（記得加入 .gitignore）
# .env 檔內容：
# LINE_CHANNEL_ACCESS_TOKEN=your_token
# LINE_CHANNEL_SECRET=your_secret
```

### 4.3 耗時操作要背景處理

Webhook 必須在短時間內回應 200 OK，否則 LINE 會重試。耗時操作（API 呼叫、DB 查詢、AI 推論）請放到背景執行。

```python
import threading

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    # 先快速回覆
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="處理中，請稍候...")],
            )
        )

    # 耗時操作放背景
    thread = threading.Thread(target=do_heavy_work, args=(event,))
    thread.start()


def do_heavy_work(event):
    result = call_expensive_api()  # 耗時操作
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.push_message(
            PushMessageRequest(
                to=event.source.user_id,
                messages=[TextMessage(text=result)],
            )
        )
```

### 4.4 其他常見問題

- **Webhook 回傳非 200**：LINE 會重試，導致重複處理。可用 `event.delivery_context.is_redelivery` 判斷是否重送
- **忘記 `return "OK"`**：Flask callback 必須回傳字串
- **HTTPS 憑證問題**：Webhook URL 必須是合法 HTTPS，開發用 ngrok

---

## 5. 事件類型列表（Webhook Events）

| 事件類型 | 類別名稱 | 說明 | 有 reply token |
|---------|----------|------|:-:|
| 訊息 | `MessageEvent` | 使用者傳送訊息 | ✅ |
| 追蹤 | `FollowEvent` | 使用者加好友 | ✅ |
| 取消追蹤 | `UnfollowEvent` | 使用者封鎖 | ❌ |
| 加入群組 | `JoinEvent` | Bot 被加入群組/聊天室 | ✅ |
| 離開群組 | `LeaveEvent` | Bot 被移出群組 | ❌ |
| 成員加入 | `MemberJoinedEvent` | 新成員加入群組 | ✅ |
| 成員離開 | `MemberLeftEvent` | 成員離開群組 | ❌ |
| Postback | `PostbackEvent` | 使用者點擊 postback 按鈕 | ✅ |
| 帳號連結 | `AccountLinkEvent` | 帳號連動結果 | ✅ |
| Beacon | `BeaconEvent` | LINE Beacon 事件 | ✅ |
| 收回訊息 | `UnsendEvent` | 使用者收回訊息 | ❌ |
| 影片播完 | `VideoPlayCompleteEvent` | 影片播放完畢 | ✅ |
| 會員 | `MembershipEvent` | 會員加入/離開/續期 | ✅ |
| 模組 | `ModuleEvent` | 模組附加/分離 | ❌ |
| Bot 暫停 | `BotSuspendedEvent` | Bot 被暫停 | ❌ |
| Bot 恢復 | `BotResumedEvent` | Bot 恢復運作 | ❌ |
| 啟用 | `ActivatedEvent` | 帳號啟用 | ❌ |
| 停用 | `DeactivatedEvent` | 帳號停用 | ❌ |
| PNP 完成 | `PnpDeliveryCompletionEvent` | 電話通知投遞完成 | ❌ |

所有事件類別從 `linebot.v3.webhooks` 匯入。

---

## 6. 訊息內容類型列表（Message Content）

| 訊息類型 | Webhook 類別（接收） | Messaging API 類別（發送） |
|---------|---------------------|--------------------------|
| 文字 | `TextMessageContent` | `TextMessage` |
| 圖片 | `ImageMessageContent` | `ImageMessage` |
| 影片 | `VideoMessageContent` | `VideoMessage` |
| 音訊 | `AudioMessageContent` | `AudioMessage` |
| 位置 | `LocationMessageContent` | `LocationMessage` |
| 貼圖 | `StickerMessageContent` | `StickerMessage` |
| 檔案 | `FileMessageContent` | —（無法主動發送） |

> **注意：接收用 `linebot.v3.webhooks`，發送用 `linebot.v3.messaging`，兩者是不同的類別。**

---

## 7. 進階：多種訊息 Handler 範例

```python
from linebot.v3.webhooks import (
    MessageEvent, FollowEvent, PostbackEvent,
    TextMessageContent, ImageMessageContent, StickerMessageContent,
)

# 文字訊息
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    pass

# 圖片訊息
@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):
    pass

# 貼圖訊息
@handler.add(MessageEvent, message=StickerMessageContent)
def handle_sticker(event):
    pass

# 追蹤事件
@handler.add(FollowEvent)
def handle_follow(event):
    pass

# Postback 事件
@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data  # 取得 postback data
    pass

# 預設 handler（未匹配的事件）
@handler.default()
def default(event):
    print(f"Unhandled event: {event}")
```

---

## 8. 專案結構建議

```
project/
├── .env                  # 環境變數（加入 .gitignore）
├── .gitignore
├── requirements.txt      # line-bot-sdk, flask, python-dotenv
├── app.py                # 主程式（webhook + handler）
└── README.md
```

`.gitignore` 必須包含：
```
.env
__pycache__/
*.pyc
```

---

## 9. 參考資源

- [line-bot-sdk-python GitHub](https://github.com/line/line-bot-sdk-python)
- [LINE Messaging API 官方文件](https://developers.line.biz/en/docs/messaging-api/overview/)
- [Webhook Event Objects](https://developers.line.biz/en/reference/messaging-api/#webhook-event-objects)
- [MessagingApi 文件](https://github.com/line/line-bot-sdk-python/blob/master/linebot/v3/messaging/docs/MessagingApi.md)
