"""
Stock AI LINE Bot — 主程式
FastAPI Webhook + line-bot-sdk-python v3 + SQLite + Gemini AI

功能：AI 股票分析師
"""

import os
import sqlite3
import logging
from contextlib import asynccontextmanager

from google import genai

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
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── LINE SDK v3 初始化 ────────────────────────────────────
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ── Gemini AI ─────────────────────────────────────────────
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"

SYSTEM_INSTRUCTION = (
    "你是一位資深證券分析師，擁有 20 年台灣與美國股市經驗。\n"
    "請遵守以下規則：\n"
    "1. 用專業但親切的語氣回覆，像在跟朋友聊天一樣\n"
    "2. 回覆必須使用繁體中文\n"
    "3. 回覆長度嚴格控制在 300 字以內，適合手機閱讀\n"
    "4. 若使用者輸入股票代號（如 2330），識別為台灣上市股票\n"
    "5. 提供重點分析：公司簡介、近期趨勢、產業展望\n"
    "6. 適當使用 emoji 讓回覆更生動\n"
    "7. 結尾務必加上：⚠️ 以上為 AI 分析，僅供參考，不構成投資建議\n"
    "8. 若問題與股票無關，友善地引導使用者詢問股票相關問題"
)


def ask_gemini(user_message: str) -> str:
    """呼叫 Gemini API 產生股票分析回覆"""
    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_message,
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                max_output_tokens=500,
            ),
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return (
            "😅 不好意思，AI 分析師目前忙碌中，請稍後再試！\n\n"
            "你可以試著：\n"
            "・稍等幾秒後重新發送\n"
            "・換個方式描述你的問題"
        )


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
    description="股票智慧助手 — AI 股票分析師",
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
    """處理文字訊息 — AI 股票分析"""
    user_id = event.source.user_id
    user_message = event.message.text

    logger.info(f"User [{user_id}] said: {user_message}")

    # 1. 記錄使用者
    upsert_user(user_id)

    # 2. 呼叫 Gemini AI 產生分析回覆
    bot_reply = ask_gemini(user_message)
    logger.info(f"Gemini replied for user [{user_id}]")

    # 3. 透過 LINE 回覆分析結果
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=bot_reply)],
            )
        )

    # 4. 儲存聊天紀錄（含 AI 分析結果）
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
        "我是你的 AI 股票分析師 📈\n"
        "輸入股票名稱或代號即可獲得分析，例如：\n"
        "・台積電\n"
        "・2330\n"
        "・分析 0050\n\n"
        "有任何股票問題都可以問我！"
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
