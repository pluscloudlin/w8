"""
Stock AI LINE Bot — 主程式
FastAPI Webhook + line-bot-sdk-python v3 + SQLite

功能：Echo Bot（鸚鵡回話）
"""

import os
import sqlite3
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException

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
    FollowEvent,
)

# ── 環境變數 ──────────────────────────────────────────────
load_dotenv()

LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
LINE_CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── LINE SDK v3 初始化 ────────────────────────────────────
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ── SQLite ────────────────────────────────────────────────
DB_PATH = "users.db"


def init_db():
    """建立資料表（若不存在）"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript("""
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
    """)
    conn.commit()
    conn.close()
    logger.info("✅ SQLite 資料庫初始化完成")


def upsert_user(user_id: str):
    """新增使用者（若已存在則更新 last_active_at）"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO users (user_id) VALUES (?)
        ON CONFLICT(user_id) DO UPDATE SET last_active_at = CURRENT_TIMESTAMP
        """,
        (user_id,),
    )
    conn.commit()
    conn.close()


def save_chat(user_id: str, user_message: str, bot_reply: str):
    """儲存聊天紀錄"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO chat_history (user_id, user_message, bot_reply) VALUES (?, ?, ?)",
        (user_id, user_message, bot_reply),
    )
    conn.commit()
    conn.close()


# ── FastAPI ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用啟動時初始化資料庫"""
    init_db()
    yield


app = FastAPI(
    title="Stock AI LINE Bot",
    description="股票智慧助手 — Echo Bot MVP",
    lifespan=lifespan,
)


@app.post("/callback")
async def callback(request: Request):
    """LINE Webhook 端點"""
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")
    logger.info("Received webhook request")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    return "OK"


# ── LINE Event Handlers ──────────────────────────────────

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """處理文字訊息 — Echo（鸚鵡回話）"""
    user_id = event.source.user_id
    user_message = event.message.text
    bot_reply = user_message  # Echo: 收到什麼回什麼

    logger.info(f"User [{user_id}] said: {user_message}")

    # 1. 記錄使用者
    upsert_user(user_id)

    # 2. 回覆訊息（使用 line-bot-sdk v3 標準寫法）
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=bot_reply)],
            )
        )

    # 3. 儲存聊天紀錄
    save_chat(user_id, user_message, bot_reply)
    logger.info(f"Chat saved for user [{user_id}]")


@handler.add(FollowEvent)
def handle_follow(event):
    """處理加入好友事件"""
    user_id = event.source.user_id
    logger.info(f"New follower: {user_id}")

    # 記錄使用者
    upsert_user(user_id)

    # 發送歡迎訊息
    welcome_message = (
        "👋 歡迎使用股票智慧助手！\n\n"
        "輸入股票名稱或代號即可查詢，例如：\n"
        "・台積電\n"
        "・2330\n"
        "・分析 0050\n\n"
        "📝 目前為 Echo 測試模式"
    )

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=welcome_message)],
            )
        )


@handler.add(MessageEvent)
def handle_non_text_message(event):
    """處理非文字訊息"""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="📝 目前僅支援文字查詢喔")],
            )
        )
