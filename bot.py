from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Awaitable, Callable

from dotenv import load_dotenv
from telegram import (
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
    User,
)
from telegram.constants import ChatMemberStatus, ChatType
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

try:
    import yt_dlp
except ImportError:  # Optional feature; the rest of the bot still works.
    yt_dlp = None

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID_RAW = os.getenv("OWNER_ID", "0").strip()
try:
    OWNER_ID = int(OWNER_ID_RAW)
except ValueError:
    OWNER_ID = 0

DB_PATH = Path(os.getenv("DB_PATH", "data/shihab.db"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("shihab")

# Telegram command names are kept in English because Bot API command names are
# ASCII-oriented. The user experience, buttons, help, and natural-language
# aliases are Arabic.
FEATURES = {
    "welcome": "الترحيب",
    "replies": "الردود",
    "protection": "الحماية",
    "antilink": "الروابط",
    "antispam": "التكرار",
    "warn": "التحذيرات",
    "mention": "المناداة",
    "youtube": "يوتيوب",
    "chat": "الدردشة",
    "photos": "الصور",
    "videos": "الفيديو",
    "audio": "الصوت",
    "voice": "الفويسات",
    "documents": "الملفات",
    "stickers": "الملصقات",
    "animations": "المتحركات",
    "forward": "التوجيه",
    "hashtags": "الهشتاق",
    "usernames": "اليوزرات",
    "contacts": "الجهات",
    "bot_add": "إضافة البوتات",
    "spam": "السبام",
    "all": "الكل",
}

FEATURE_ALIASES = {
    **{key: key for key in FEATURES},
    **{label: key for key, label in FEATURES.items()},
    "الرابط": "antilink",
    "اللينك": "antilink",
    "التكرار": "antispam",
    "الاضافة": "bot_add",
    "الإضافة": "bot_add",
    "البوتات": "bot_add",
    "الدردشه": "chat",
    "الدردشة": "chat",
    "الملفات": "documents",
    "المتحركات": "animations",
    "الفيديوهات": "videos",
    "الصور": "photos",
    "الصوتيات": "audio",
    "الاشعارات": "chat",
    "الإشعارات": "chat",
    "الانلاين": "usernames",
    "الجهات": "contacts",
}

BUILTIN_REPLIES = {
    "كيفك": ["بخير دامك بخير، وش أخبارك؟", "تمام التمام، شهاب حاضر.", "الحمدلله بخير، نورت المجموعة."],
    "تعال": ["جيتك، تفضل.", "حاضر، شهاب موجود.", "سمّ، وش تحتاج؟"],
    "خاص": ["إذا عندك أمر للمالك استخدم القائمة الخاصة بالبوت.", "تفضل، اكتب لي في الخاص إذا كانت المحادثة مفتوحة."],
    "وينك": ["هنا، أراقب المجموعة بهدوء.", "موجود وما فاتني شيء.", "شهاب حاضر بينكم."],
    "احبك": ["المحبة متبادلة يا محترم.", "تسلم، كلامك جميل.", "وأنا أقدّر ذوقك."],
}
MENTION_REPLIES = [
    "نعم؟ شهاب حاضر.",
    "سمّ، أسمعك.",
    "تفضل، ما الأمر؟",
    "حاضر يا غالي، قل لي.",
    "موجود، لكن بدون إزعاج للمجموعة.",
]

LOCKABLE_MEDIA = {
    "photos": lambda m: bool(m.photo),
    "videos": lambda m: bool(m.video),
    "audio": lambda m: bool(m.audio),
    "voice": lambda m: bool(m.voice),
    "documents": lambda m: bool(m.document),
    "stickers": lambda m: bool(m.sticker),
    "animations": lambda m: bool(m.animation),
    "forward": lambda m: m.forward_origin is not None,
    "contacts": lambda m: bool(m.contact or m.location or m.venue),
}
LOCK_FEATURES = set(LOCKABLE_MEDIA) | {"chat", "bot_add"}

URL_RE = re.compile(r"(?:https?://|www\.)\S+|(?:[a-z0-9-]+\.)+(?:com|net|org|io|me|co|tv)\b", re.I)
MENTION_WORDS = ("شهاب", "شاخوف", "بوت")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=20)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT NOT NULL,
                    username TEXT,
                    first_seen TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS groups_info (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    first_seen TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    chat_id INTEGER NOT NULL,
                    feature TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (chat_id, feature)
                );
                CREATE TABLE IF NOT EXISTS texts (
                    chat_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    value TEXT,
                    PRIMARY KEY (chat_id, name)
                );
                CREATE TABLE IF NOT EXISTS warnings (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (chat_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS muted (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    until_ts INTEGER NOT NULL,
                    PRIMARY KEY (chat_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS jailed (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    PRIMARY KEY (chat_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS custom_replies (
                    chat_id INTEGER NOT NULL,
                    keyword TEXT NOT NULL,
                    reply TEXT NOT NULL,
                    PRIMARY KEY (chat_id, keyword)
                );
                CREATE TABLE IF NOT EXISTS custom_commands (
                    chat_id INTEGER NOT NULL,
                    command TEXT NOT NULL,
                    response TEXT NOT NULL,
                    PRIMARY KEY (chat_id, command)
                );
                CREATE TABLE IF NOT EXISTS rank_members (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    rank TEXT NOT NULL,
                    assigned_at TEXT NOT NULL,
                    PRIMARY KEY (chat_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS group_plans (
                    chat_id INTEGER PRIMARY KEY,
                    plan TEXT NOT NULL DEFAULT 'free',
                    expires_at INTEGER,
                    updated_by INTEGER,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS owner_assistants (
                    user_id INTEGER PRIMARY KEY,
                    added_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS global_bans (
                    user_id INTEGER PRIMARY KEY,
                    reason TEXT,
                    banned_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    actor_id INTEGER,
                    event TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def register(self, user_id: int | None, first_name: str | None, username: str | None, chat_id: int | None, chat_title: str | None) -> None:
        with self.connect() as conn:
            if user_id is not None:
                conn.execute(
                    "INSERT INTO users(user_id, first_name, username, first_seen) VALUES(?,?,?,?) "
                    "ON CONFLICT(user_id) DO UPDATE SET first_name=excluded.first_name, username=excluded.username",
                    (user_id, first_name or "مستخدم", username, utc_now()),
                )
            if chat_id is not None and chat_title is not None and chat_id < 0:
                conn.execute(
                    "INSERT INTO groups_info(chat_id, title, first_seen) VALUES(?,?,?) "
                    "ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title",
                    (chat_id, chat_title, utc_now()),
                )
                for feature in FEATURES:
                    conn.execute("INSERT OR IGNORE INTO settings(chat_id, feature, enabled) VALUES(?,?,1)", (chat_id, feature))

    def feature(self, chat_id: int, name: str, default: int = 1) -> bool:
        key = FEATURE_ALIASES.get(normalize(name), normalize(name))
        with self.connect() as conn:
            row = conn.execute("SELECT enabled FROM settings WHERE chat_id=? AND feature=?", (chat_id, key)).fetchone()
            return bool(row["enabled"]) if row else bool(default)

    def set_feature(self, chat_id: int, name: str, enabled: bool) -> str:
        key = FEATURE_ALIASES.get(normalize(name), normalize(name))
        if key not in FEATURES:
            raise ValueError("الميزة غير معروفة")
        with self.connect() as conn:
            conn.execute("INSERT INTO settings(chat_id, feature, enabled) VALUES(?,?,?) ON CONFLICT(chat_id,feature) DO UPDATE SET enabled=excluded.enabled", (chat_id, key, int(enabled)))
        return key

    def all_features(self, chat_id: int) -> dict[str, bool]:
        with self.connect() as conn:
            rows = conn.execute("SELECT feature, enabled FROM settings WHERE chat_id=?", (chat_id,)).fetchall()
        result = {key: True for key in FEATURES}
        result.update({row["feature"]: bool(row["enabled"]) for row in rows})
        return result

    def set_text(self, chat_id: int, name: str, value: str | None) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO texts(chat_id,name,value) VALUES(?,?,?) ON CONFLICT(chat_id,name) DO UPDATE SET value=excluded.value", (chat_id, name, value))

    def get_text(self, chat_id: int, name: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM texts WHERE chat_id=? AND name=?", (chat_id, name)).fetchone()
        return row["value"] if row else None

    def add_warning(self, chat_id: int, user_id: int) -> int:
        with self.connect() as conn:
            conn.execute("INSERT INTO warnings(chat_id,user_id,count) VALUES(?,?,1) ON CONFLICT(chat_id,user_id) DO UPDATE SET count=count+1", (chat_id, user_id))
            row = conn.execute("SELECT count FROM warnings WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
        return int(row["count"])

    def warnings(self, chat_id: int, user_id: int) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT count FROM warnings WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
        return int(row["count"]) if row else 0

    def reset_warnings(self, chat_id: int, user_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM warnings WHERE chat_id=? AND user_id=?", (chat_id, user_id))

    def set_mute(self, chat_id: int, user_id: int, until_ts: int) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO muted(chat_id,user_id,until_ts) VALUES(?,?,?) ON CONFLICT(chat_id,user_id) DO UPDATE SET until_ts=excluded.until_ts", (chat_id, user_id, until_ts))

    def mute_until(self, chat_id: int, user_id: int) -> int | None:
        with self.connect() as conn:
            row = conn.execute("SELECT until_ts FROM muted WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
        return int(row["until_ts"]) if row else None

    def clear_mute(self, chat_id: int, user_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM muted WHERE chat_id=? AND user_id=?", (chat_id, user_id))

    def muted_users(self, chat_id: int) -> list[int]:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        with self.connect() as conn:
            rows = conn.execute("SELECT user_id FROM muted WHERE chat_id=? AND until_ts>? ORDER BY until_ts", (chat_id, now_ts)).fetchall()
        return [int(row["user_id"]) for row in rows]

    def jailed_users(self, chat_id: int) -> list[int]:
        with self.connect() as conn:
            rows = conn.execute("SELECT user_id FROM jailed WHERE chat_id=? ORDER BY user_id", (chat_id,)).fetchall()
        return [int(row["user_id"]) for row in rows]

    def set_jailed(self, chat_id: int, user_id: int, value: bool) -> None:
        with self.connect() as conn:
            if value:
                conn.execute("INSERT OR IGNORE INTO jailed(chat_id,user_id) VALUES(?,?)", (chat_id, user_id))
            else:
                conn.execute("DELETE FROM jailed WHERE chat_id=? AND user_id=?", (chat_id, user_id))

    def is_jailed(self, chat_id: int, user_id: int) -> bool:
        with self.connect() as conn:
            return conn.execute("SELECT 1 FROM jailed WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone() is not None

    def add_reply(self, chat_id: int, keyword: str, reply: str) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO custom_replies(chat_id,keyword,reply) VALUES(?,?,?) ON CONFLICT(chat_id,keyword) DO UPDATE SET reply=excluded.reply", (chat_id, normalize(keyword), reply.strip()))

    def get_reply(self, chat_id: int, keyword: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT reply FROM custom_replies WHERE chat_id=? AND keyword=?", (chat_id, normalize(keyword))).fetchone()
        return row["reply"] if row else None

    def replies(self, chat_id: int) -> list[tuple[str, str]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT keyword,reply FROM custom_replies WHERE chat_id=? ORDER BY keyword", (chat_id,)).fetchall()
        return [(row["keyword"], row["reply"]) for row in rows]

    def delete_reply(self, chat_id: int, keyword: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM custom_replies WHERE chat_id=? AND keyword=?", (chat_id, normalize(keyword)))

    def delete_all_replies(self, chat_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM custom_replies WHERE chat_id=?", (chat_id,))

    def add_command(self, chat_id: int, command: str, response: str) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO custom_commands(chat_id,command,response) VALUES(?,?,?) ON CONFLICT(chat_id,command) DO UPDATE SET response=excluded.response", (chat_id, normalize(command), response.strip()))

    def command_response(self, chat_id: int, command: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT response FROM custom_commands WHERE chat_id=? AND command=?", (chat_id, normalize(command))).fetchone()
        return row["response"] if row else None

    def set_plan(self, chat_id: int, plan: str, days: int | None, actor_id: int) -> None:
        expires_at = int(datetime.now(timezone.utc).timestamp()) + days * 86400 if days else None
        with self.connect() as conn:
            conn.execute("INSERT INTO group_plans(chat_id,plan,expires_at,updated_by,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(chat_id) DO UPDATE SET plan=excluded.plan, expires_at=excluded.expires_at, updated_by=excluded.updated_by, updated_at=excluded.updated_at", (chat_id, plan, expires_at, actor_id, utc_now()))

    def charge_plan(self, chat_id: int, days: int, actor_id: int) -> int:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        with self.connect() as conn:
            row = conn.execute("SELECT expires_at FROM group_plans WHERE chat_id=?", (chat_id,)).fetchone()
            base = max(now_ts, int(row["expires_at"]) if row and row["expires_at"] else now_ts)
            expires_at = base + days * 86400
            conn.execute("INSERT INTO group_plans(chat_id,plan,expires_at,updated_by,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(chat_id) DO UPDATE SET expires_at=excluded.expires_at, updated_by=excluded.updated_by, updated_at=excluded.updated_at", (chat_id, "vip", expires_at, actor_id, utc_now()))
        return expires_at

    def plan_info(self, chat_id: int) -> tuple[str, int | None]:
        with self.connect() as conn:
            row = conn.execute("SELECT plan,expires_at FROM group_plans WHERE chat_id=?", (chat_id,)).fetchone()
        if not row:
            return "free", None
        return str(row["plan"]), int(row["expires_at"]) if row["expires_at"] else None

    def plan_counts(self) -> dict[str, int]:
        with self.connect() as conn:
            rows = conn.execute("SELECT plan,COUNT(*) AS n FROM group_plans GROUP BY plan").fetchall()
        return {str(row["plan"]): int(row["n"]) for row in rows}

    def group_ids(self, plan: str | None = None) -> list[int]:
        with self.connect() as conn:
            if plan:
                rows = conn.execute("SELECT g.chat_id FROM groups_info g JOIN group_plans p ON p.chat_id=g.chat_id WHERE p.plan=?", (plan,)).fetchall()
            else:
                rows = conn.execute("SELECT chat_id FROM groups_info").fetchall()
        return [int(row["chat_id"]) for row in rows]

    def set_rank(self, chat_id: int, user_id: int, rank: str | None) -> None:
        with self.connect() as conn:
            if rank:
                conn.execute("INSERT INTO rank_members(chat_id,user_id,rank,assigned_at) VALUES(?,?,?,?) ON CONFLICT(chat_id,user_id) DO UPDATE SET rank=excluded.rank, assigned_at=excluded.assigned_at", (chat_id, user_id, rank, utc_now()))
            else:
                conn.execute("DELETE FROM rank_members WHERE chat_id=? AND user_id=?", (chat_id, user_id))

    def get_rank(self, chat_id: int, user_id: int) -> str | None:
        with self.connect() as conn:
            row = conn.execute("SELECT rank FROM rank_members WHERE chat_id=? AND user_id=?", (chat_id, user_id)).fetchone()
        return row["rank"] if row else None

    def ranked_users(self, chat_id: int, rank: str | None = None) -> list[int]:
        with self.connect() as conn:
            if rank:
                rows = conn.execute("SELECT user_id FROM rank_members WHERE chat_id=? AND rank=?", (chat_id, rank)).fetchall()
            else:
                rows = conn.execute("SELECT user_id FROM rank_members WHERE chat_id=?", (chat_id,)).fetchall()
        return [int(row["user_id"]) for row in rows]

    def set_assistant(self, user_id: int, enabled: bool) -> None:
        with self.connect() as conn:
            if enabled:
                conn.execute("INSERT OR IGNORE INTO owner_assistants(user_id,added_at) VALUES(?,?)", (user_id, utc_now()))
            else:
                conn.execute("DELETE FROM owner_assistants WHERE user_id=?", (user_id,))

    def is_assistant(self, user_id: int) -> bool:
        with self.connect() as conn:
            return conn.execute("SELECT 1 FROM owner_assistants WHERE user_id=?", (user_id,)).fetchone() is not None

    def assistants(self) -> list[int]:
        with self.connect() as conn:
            return [int(row["user_id"]) for row in conn.execute("SELECT user_id FROM owner_assistants ORDER BY added_at")]

    def set_global_ban(self, user_id: int, reason: str | None, enabled: bool) -> None:
        with self.connect() as conn:
            if enabled:
                conn.execute("INSERT INTO global_bans(user_id,reason,banned_at) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET reason=excluded.reason", (user_id, reason, utc_now()))
            else:
                conn.execute("DELETE FROM global_bans WHERE user_id=?", (user_id,))

    def is_global_banned(self, user_id: int) -> bool:
        with self.connect() as conn:
            return conn.execute("SELECT 1 FROM global_bans WHERE user_id=?", (user_id,)).fetchone() is not None

    def global_bans(self) -> list[int]:
        with self.connect() as conn:
            return [int(row["user_id"]) for row in conn.execute("SELECT user_id FROM global_bans ORDER BY banned_at")]

    def log(self, chat_id: int | None, actor_id: int | None, event: str) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO event_log(chat_id,actor_id,event,created_at) VALUES(?,?,?,?)", (chat_id, actor_id, event, utc_now()))

    def stats(self) -> dict[str, int]:
        with self.connect() as conn:
            users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
            groups = conn.execute("SELECT COUNT(*) AS n FROM groups_info").fetchone()["n"]
            events = conn.execute("SELECT COUNT(*) AS n FROM event_log").fetchone()["n"]
        return {"users": users, "groups": groups, "events": events}

    def find_user(self, identifier: str) -> sqlite3.Row | None:
        identifier = identifier.strip().lstrip("@")
        with self.connect() as conn:
            if identifier.isdigit():
                return conn.execute("SELECT user_id,first_name,username FROM users WHERE user_id=?", (int(identifier),)).fetchone()
            return conn.execute("SELECT user_id,first_name,username FROM users WHERE lower(username)=lower(?)", (identifier,)).fetchone()

    def user_ids(self) -> list[int]:
        with self.connect() as conn:
            return [int(row["user_id"]) for row in conn.execute("SELECT user_id FROM users")]


db = Database(DB_PATH)


def group_only(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any) -> Any:
        if update.effective_chat is None or update.effective_chat.type == ChatType.PRIVATE:
            if update.effective_message:
                await update.effective_message.reply_text("هذا الأمر يعمل داخل المجموعات فقط.")
            return None
        return await func(update, context, *args, **kwargs)
    return wrapper


async def is_admin(update: Update, user_id: int | None = None) -> bool:
    chat = update.effective_chat
    if not chat or chat.type == ChatType.PRIVATE:
        return False
    user_id = user_id or (update.effective_user.id if update.effective_user else 0)
    try:
        member = await chat.get_member(user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except TelegramError:
        return False


async def bot_is_admin(update: Update) -> bool:
    chat = update.effective_chat
    if not chat or chat.type == ChatType.PRIVATE:
        return False
    try:
        member = await chat.get_member((await update.get_bot()).id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except TelegramError:
        return False


async def admin_required(update: Update) -> bool:
    if await is_admin(update):
        if await bot_is_admin(update):
            return True
        await update.effective_message.reply_text("ارفعني مشرفاً مع صلاحية حذف الرسائل وتقييد الأعضاء أولاً.")
        return False
    await update.effective_message.reply_text("هذا الأمر للمشرفين فقط.")
    return False


async def target_from_reply(update: Update, identifiers: list[str] | None = None) -> Any | None:
    message = update.effective_message
    if message and message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    for identifier in identifiers or []:
        row = db.find_user(identifier)
        if row:
            return User(id=int(row["user_id"]), first_name=row["first_name"] or "مستخدم", is_bot=False, username=row["username"])
    if message:
        await message.reply_text("استخدم الأمر بالرد على رسالة العضو أو اكتب رقمه/معرفه بعد أن يتفاعل مع البوت.")
    return None


async def safe_delete(message: Message | None) -> None:
    if not message:
        return
    try:
        await message.delete()
    except TelegramError:
        logger.debug("Could not delete message", exc_info=True)


async def full_permissions() -> ChatPermissions:
    # all_permissions is present in current python-telegram-bot releases; the
    # fallback keeps compatibility with older Termux installations.
    factory = getattr(ChatPermissions, "all_permissions", None)
    if callable(factory):
        return factory()
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_add_web_page_previews=True,
        can_invite_users=True,
        can_change_info=False,
        can_pin_messages=False,
        can_manage_topics=True,
    )


async def restrict_member(chat: Any, user_id: int, **kwargs: Any) -> None:
    await chat.restrict_chat_member(user_id, permissions=ChatPermissions(**kwargs))


async def command_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_chat or not update.effective_message:
        return
    db.register(update.effective_user.id, update.effective_user.first_name, update.effective_user.username, update.effective_chat.id, update.effective_chat.title or "")
    await update.effective_message.reply_text(
        "مرحباً بك في شهاب.\n\nأنا مدير مجموعات عربي عملي: حماية، صلاحيات، ردود، ترحيب، إعدادات، وإحصائيات.\nاختر من القائمة أو استخدم /help.",
        reply_markup=main_keyboard(update.effective_user.id == OWNER_ID),
    )


def main_keyboard(is_owner: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("الأوامر", callback_data="home:commands"), InlineKeyboardButton("الخدمات", callback_data="home:services")],
        [InlineKeyboardButton("الإعدادات", callback_data="home:settings"), InlineKeyboardButton("عن شهاب", callback_data="home:about")],
    ]
    if is_owner:
        rows.append([InlineKeyboardButton("لوحة المالك", callback_data="owner:home")])
    return InlineKeyboardMarkup(rows)


def commands_text() -> str:
    return (
        "قائمة الأوامر الأساسية\n\n"
        "الإدارة بالرد على رسالة:\n"
        "/kick  /ban  /unban ID  /mute دقائق  /unmute\n"
        "/warn  /warns  /resetwarns  /jail  /unjail  /restrict\n\n"
        "الإعدادات:\n"
        "/lock feature  /unlock feature\n"
        "/enable feature  /disable feature\n"
        "/setwelcome نص  /delwelcome  /setrules نص  /rules\n\n"
        "الردود والخدمات:\n"
        "    /addreply كلمة | الرد  /replies  /delreply كلمة  /delallreplies\n"
        "/addcmd أمر | الرد  /delcmd أمر\n"
        "/id  /age  /bio  /services  /whisper\n"
        "/search اسم فيديو  /yt رابط فيديو\n\n"
        "أوامر عربية مباشرة داخل المجموعة:\n"
        "طرد، حظر، رفع الحظر، كتم 10، فك الكتم، سجن، فك السجن، تقييد، تحذير، التحذيرات.\n"
        "رفع مشرف، إزالة مشرف، تغيير رتبة مدير، المشرفين، المميزين، صلاحياتي، معلومات المجموعة.\n"
        "بحث اسم الفيديو، يوت رابط الفيديو، قفل الصور، فتح الروابط، تفعيل الترحيب، تعطيل التكرار.\n\n"
        "بدون شرطة مائلة أيضاً: قفل الروابط، فتح الصور، تفعيل الترحيب، تعطيل التكرار."
    )


def services_text() -> str:
    return (
        "خدمات شهاب\n\n"
        "حماية الروابط والسبام، منع أنواع الوسائط، نظام التحذيرات، الكتم المؤقت، السجن، الترحيب، القوانين، الردود المخصصة، الأوامر المخصصة، معلومات الأعضاء، لوحة المالك، وبحث يوتيوب اختياري.\n\n"
        "كل إعداد مستقل لكل مجموعة، وصلاحيات الإدارة تُفحص من تيليجرام قبل أي إجراء."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(commands_text())


async def services_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(services_text())


@group_only
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    features = db.all_features(update.effective_chat.id)
    lines = ["إعدادات هذه المجموعة:"]
    for key, label in FEATURES.items():
        lines.append(f"{'مفتوح' if features.get(key, True) else 'مغلق'} — {label} ({key})")
    await update.effective_message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("تحديث الإعدادات", callback_data="home:settings")]]))


@group_only
async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, arabic_args: list[str] | None = None, target_override: Any | None = None) -> None:
    if not await admin_required(update):
        return
    target = target_override or await target_from_reply(update, arabic_args if action != "mute" else None)
    if not target:
        return
    if target.id == update.effective_user.id:
        await update.effective_message.reply_text("لا يمكنك تنفيذ هذا الإجراء على نفسك.")
        return
    if await is_admin(update, target.id):
        await update.effective_message.reply_text("لا أغيّر صلاحيات المشرفين أو المالكين.")
        return
    chat = update.effective_chat
    try:
        if action == "kick":
            await chat.ban_member(target.id)
            await chat.unban_member(target.id)
            text = f"تم طرد {target.first_name}."
        elif action == "ban":
            await chat.ban_member(target.id)
            text = f"تم حظر {target.first_name}."
        elif action == "unban":
            raise ValueError("لإلغاء الحظر استخدم /unban مع رقم المستخدم.")
        elif action == "mute":
            args = arabic_args if arabic_args is not None else context.args
            minutes = max(1, min(int(args[0]) if args else 10, 10080))
            until = int(datetime.now(timezone.utc).timestamp()) + minutes * 60
            db.set_mute(chat.id, target.id, until)
            await restrict_member(chat, target.id, can_send_messages=False)
            if context.job_queue:
                context.job_queue.run_once(unmute_job, minutes * 60, data=(chat.id, target.id))
            text = f"تم كتم {target.first_name} لمدة {minutes} دقيقة."
        elif action == "unmute":
            db.clear_mute(chat.id, target.id)
            await chat.restrict_chat_member(target.id, permissions=await full_permissions())
            text = f"تم إلغاء كتم {target.first_name}."
        elif action == "jail":
            db.set_jailed(chat.id, target.id, True)
            await restrict_member(chat, target.id, can_send_messages=False)
            text = f"تم سجن {target.first_name}."
        elif action == "unjail":
            db.set_jailed(chat.id, target.id, False)
            await chat.restrict_chat_member(target.id, permissions=await full_permissions())
            text = f"تم إخراج {target.first_name} من السجن."
        elif action == "restrict":
            await restrict_member(chat, target.id, can_send_messages=True, can_send_audios=False, can_send_documents=False, can_send_photos=False, can_send_videos=False, can_send_video_notes=False, can_send_voice_notes=False, can_send_polls=False, can_add_web_page_previews=False)
            text = f"تم تقييد وسائط {target.first_name}."
        else:
            return
        db.log(chat.id, update.effective_user.id, f"{action}:{target.id}")
        await update.effective_message.reply_text(text)
    except (TelegramError, ValueError) as exc:
        await update.effective_message.reply_text(f"تعذر تنفيذ الإجراء: {exc}")


@group_only
async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_required(update):
        return
    target = await target_from_reply(update)
    if not target:
        return
    if await is_admin(update, target.id):
        await update.effective_message.reply_text("لا أضع تحذيرات على المشرفين.")
        return
    count = db.add_warning(update.effective_chat.id, target.id)
    await update.effective_message.reply_text(f"تحذير {target.first_name}: {count}/3")
    if count >= 3:
        try:
            await update.effective_chat.ban_member(target.id)
            db.reset_warnings(update.effective_chat.id, target.id)
            await update.effective_message.reply_text(f"تجاوز الحد، تم حظر {target.first_name} تلقائياً.")
        except TelegramError as exc:
            await update.effective_message.reply_text(f"وصل للحد الأقصى لكن تعذر الحظر: {exc}")


@group_only
async def warns_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await target_from_reply(update)
    if target:
        count = db.warnings(update.effective_chat.id, target.id)
        await update.effective_message.reply_text(f"لدى {target.first_name} عدد {count} تحذير.")


@group_only
async def reset_warns_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_required(update):
        return
    target = await target_from_reply(update)
    if target:
        db.reset_warnings(update.effective_chat.id, target.id)
        await update.effective_message.reply_text(f"تم تصفير تحذيرات {target.first_name}.")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or update.effective_chat.type == ChatType.PRIVATE:
        return
    if not await admin_required(update) or not context.args:
        if not context.args and update.effective_message:
            await update.effective_message.reply_text("استخدم /unban رقم_المستخدم.")
        return
    try:
        await update.effective_chat.unban_member(int(context.args[0]))
        await update.effective_message.reply_text("تم إلغاء الحظر.")
    except (ValueError, TelegramError) as exc:
        await update.effective_message.reply_text(f"تعذر إلغاء الحظر: {exc}")


async def unmute_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id, user_id = context.job.data
    try:
        db.clear_mute(chat_id, user_id)
        await context.bot.restrict_chat_member(chat_id, user_id, permissions=await full_permissions())
    except TelegramError:
        logger.debug("Scheduled unmute failed", exc_info=True)


@group_only
async def set_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str, arabic_value: str | None = None) -> None:
    if not await admin_required(update):
        return
    value = (arabic_value if arabic_value is not None else " ".join(context.args)).strip()
    if not value:
        await update.effective_message.reply_text(f"استخدم الأمر مع نص، مثال: /{name} أهلاً {{name}}")
        return
    db.set_text(update.effective_chat.id, name, value)
    await update.effective_message.reply_text(f"تم حفظ {name}.")


@group_only
async def delete_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str) -> None:
    if not await admin_required(update):
        return
    db.set_text(update.effective_chat.id, name, None)
    await update.effective_message.reply_text("تم الحذف.")


@group_only
async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rules = db.get_text(update.effective_chat.id, "rules")
    await update.effective_message.reply_text(rules or "لم تُعيّن قوانين لهذه المجموعة بعد.")


@group_only
async def toggle_command(update: Update, context: ContextTypes.DEFAULT_TYPE, enabled: bool) -> None:
    if not await admin_required(update):
        return
    if not context.args:
        await update.effective_message.reply_text("استخدم اسم الميزة، مثل: /enable antilink")
        return
    raw = normalize(context.args[0])
    key = FEATURE_ALIASES.get(raw, raw)
    if key not in FEATURES:
        await update.effective_message.reply_text("الميزة غير معروفة. استخدم /settings لرؤية الأسماء.")
        return
    db.set_feature(update.effective_chat.id, key, enabled)
    await update.effective_message.reply_text(f"تم {'تفعيل' if enabled else 'تعطيل'} {FEATURES[key]}.")


@group_only
async def lock_command(update: Update, context: ContextTypes.DEFAULT_TYPE, enabled: bool) -> None:
    if not await admin_required(update):
        return
    if not context.args:
        await update.effective_message.reply_text("استخدم /lock feature أو /unlock feature. مثال: /lock photos")
        return
    raw = normalize(context.args[0])
    key = FEATURE_ALIASES.get(raw, raw)
    if key not in FEATURES:
        await update.effective_message.reply_text("الميزة غير معروفة. استخدم /settings.")
        return
    if key == "all":
        for feature_name in LOCK_FEATURES:
            db.set_feature(update.effective_chat.id, feature_name, enabled)
    else:
        db.set_feature(update.effective_chat.id, key, not enabled)
    await update.effective_message.reply_text(f"تم {'فتح' if enabled else 'قفل'} {FEATURES[key]}.")


@group_only
async def add_reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE, arabic_raw: str | None = None) -> None:
    if not await admin_required(update):
        return
    raw = arabic_raw if arabic_raw is not None else " ".join(context.args)
    if "|" not in raw:
        await update.effective_message.reply_text("استخدم: /addreply كلمة | نص الرد")
        return
    keyword, reply = raw.split("|", 1)
    if not keyword.strip() or not reply.strip():
        await update.effective_message.reply_text("يجب كتابة الكلمة والرد.")
        return
    db.add_reply(update.effective_chat.id, keyword, reply)
    await update.effective_message.reply_text(f"تم حفظ رد كلمة: {keyword.strip()}")


@group_only
async def replies_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = db.replies(update.effective_chat.id)
    if not rows:
        await update.effective_message.reply_text("لا توجد ردود مخصصة.")
        return
    await update.effective_message.reply_text("الردود المخصصة:\n" + "\n".join(f"• {key} ← {value}" for key, value in rows))


@group_only
async def del_reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE, arabic_keyword: str | None = None) -> None:
    if not await admin_required(update):
        return
    keyword = arabic_keyword if arabic_keyword is not None else (context.args[0] if context.args else "")
    if not keyword:
        await update.effective_message.reply_text("استخدم /delreply كلمة")
        return
    db.delete_reply(update.effective_chat.id, keyword)
    await update.effective_message.reply_text("تم حذف الرد إن كان موجوداً.")


@group_only
async def del_all_replies_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_required(update):
        return
    db.delete_all_replies(update.effective_chat.id)
    await update.effective_message.reply_text("تم حذف جميع الردود.")


@group_only
async def add_command_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_required(update):
        return
    raw = " ".join(context.args)
    if "|" not in raw:
        await update.effective_message.reply_text("استخدم: /addcmd اسم_الأمر | نص الرد")
        return
    command, response = raw.split("|", 1)
    command = normalize(command).lstrip("/")
    if not command or not response.strip():
        await update.effective_message.reply_text("يجب كتابة اسم الأمر والرد.")
        return
    db.add_command(update.effective_chat.id, command, response)
    await update.effective_message.reply_text(f"تم حفظ الأمر المخصص: {command}")


@group_only
async def del_command_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await admin_required(update):
        return
    if not context.args:
        await update.effective_message.reply_text("استخدم /delcmd اسم_الأمر")
        return
    with db.connect() as conn:
        conn.execute("DELETE FROM custom_commands WHERE chat_id=? AND command=?", (update.effective_chat.id, normalize(context.args[0]).lstrip("/")))
    await update.effective_message.reply_text("تم حذف الأمر إن كان موجوداً.")


async def identity_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    await update.effective_message.reply_text(f"الاسم: {user.full_name}\nالمعرف الرقمي: {user.id}\nالمستخدم: @{user.username or 'لا يوجد'}")


async def member_status_text(update: Update, user_id: int) -> str:
    chat = update.effective_chat
    if not chat:
        return "غير معروف"
    try:
        member = await chat.get_member(user_id)
    except TelegramError:
        return "تعذر جلب الصلاحيات"
    labels = {
        ChatMemberStatus.OWNER: "مالك المجموعة",
        ChatMemberStatus.ADMINISTRATOR: "مشرف",
        ChatMemberStatus.MEMBER: "عضو",
        ChatMemberStatus.RESTRICTED: "مقيّد",
        ChatMemberStatus.LEFT: "غادر",
        ChatMemberStatus.BANNED: "محظور",
    }
    label = labels.get(member.status, member.status)
    title = getattr(member, "custom_title", None)
    return f"{label}{f' — {title}' if title else ''}"


async def permissions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or update.effective_chat.type == ChatType.PRIVATE:
        await update.effective_message.reply_text("هذا الأمر يعمل داخل المجموعة.")
        return
    target = update.effective_message.reply_to_message.from_user if update.effective_message.reply_to_message and update.effective_message.reply_to_message.from_user else update.effective_user
    if not target:
        return
    status = await member_status_text(update, target.id)
    rank = db.get_rank(update.effective_chat.id, target.id)
    warns = db.warnings(update.effective_chat.id, target.id)
    await update.effective_message.reply_text(f"معلومات {target.first_name}:\\nالحالة: {status}\\nالرتبة: {rank or 'عضو'}\\nالتحذيرات: {warns}\\nالمعرف: {target.id}")


@group_only
async def set_rank_command(update: Update, context: ContextTypes.DEFAULT_TYPE, rank: str | None = None) -> None:
    if not await admin_required(update):
        return
    target = await target_from_reply(update)
    if not target:
        return
    chosen = (rank or (context.args[0] if context.args else "")).strip()
    aliases = {"مدير": "مدير", "ادمن": "ادمن", "أدمن": "ادمن", "مميز": "مميز", "مشرف": "مشرف", "عضو": None, "حذف": None, "إزالة": None}
    if chosen not in aliases:
        await update.effective_message.reply_text("الرتب المتاحة: مدير، ادمن، مميز، مشرف، عضو.")
        return
    db.set_rank(update.effective_chat.id, target.id, aliases[chosen])
    await update.effective_message.reply_text(f"تم {'إزالة رتبة' if aliases[chosen] is None else 'تعيين رتبة ' + aliases[chosen]} لـ {target.first_name}.")


@group_only
async def list_people_command(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str) -> None:
    chat = update.effective_chat
    if category == "ranked":
        ids = db.ranked_users(chat.id)
        title = "أصحاب الرتب المخصصة"
    elif category == "muted":
        ids = db.muted_users(chat.id)
        title = "المكتومون"
    else:
        ids = db.jailed_users(chat.id)
        title = "المسجونون"
    if not ids:
        await update.effective_message.reply_text(f"{title}: لا توجد سجلات.")
        return
    lines = []
    for user_id in ids[:50]:
        try:
            member = await chat.get_member(user_id)
            lines.append(f"• {member.user.first_name} — {user_id}")
        except TelegramError:
            lines.append(f"• {user_id}")
    await update.effective_message.reply_text(f"{title}:\\n" + "\\n".join(lines))


@group_only
async def promote_arabic_command(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str, identifiers: list[str] | None = None) -> None:
    if not await admin_required(update):
        return
    target = await target_from_reply(update, identifiers or [])
    if not target:
        return
    if await is_admin(update, target.id):
        await update.effective_message.reply_text("العضو مشرف بالفعل أو لا يمكن تعديل صلاحياته.")
        return
    try:
        if mode == "demote":
            await context.bot.promote_chat_member(update.effective_chat.id, target.id, can_change_info=False, can_delete_messages=False, can_invite_users=False, can_restrict_members=False, can_pin_messages=False, can_promote_members=False, can_manage_video_chats=False, can_manage_topics=False)
            await update.effective_message.reply_text(f"تم إزالة إشراف {target.first_name}.")
        else:
            await context.bot.promote_chat_member(update.effective_chat.id, target.id, can_change_info=(mode == "manager"), can_delete_messages=True, can_invite_users=True, can_restrict_members=True, can_pin_messages=(mode == "manager"), can_promote_members=False, can_manage_video_chats=True, can_manage_topics=True)
            await update.effective_message.reply_text(f"تم رفع {target.first_name} مشرفاً بصلاحيات واقعية.")
        db.log(update.effective_chat.id, update.effective_user.id, f"{mode}:{target.id}")
    except TelegramError as exc:
        await update.effective_message.reply_text(f"تعذر تغيير الصلاحيات: {exc}")


async def admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or update.effective_chat.type == ChatType.PRIVATE:
        return
    try:
        admins = await update.effective_chat.get_administrators()
        lines = [f"• {member.user.first_name} — {member.user.id}" for member in admins]
        await update.effective_message.reply_text("مشرفو المجموعة:\\n" + "\\n".join(lines))
    except TelegramError as exc:
        await update.effective_message.reply_text(f"تعذر جلب المشرفين: {exc}")


@group_only
async def group_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    admins = await chat.get_administrators()
    features = db.all_features(chat.id)
    enabled = sum(1 for value in features.values() if value)
    await update.effective_message.reply_text(f"معلومات المجموعة\\n\\nالاسم: {chat.title or 'بدون اسم'}\\nالمعرف: {chat.id}\\nالمشرفون: {len(admins)}\\nالإعدادات المفتوحة: {enabled}/{len(FEATURES)}\\nالرابط العام: {('@' + chat.username) if chat.username else 'لا يوجد'}")


async def date_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE, date_only: bool = False) -> None:
    now = datetime.now().astimezone()
    await update.effective_message.reply_text(now.strftime("التاريخ: %Y-%m-%d" if date_only else "الساعة: %H:%M:%S\\nالتاريخ: %Y-%m-%d"))


async def age_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    await update.effective_message.reply_text("تيليجرام لا يرسل للبوت تاريخ إنشاء الحساب الحقيقي. أستطيع عرض معرفك وتاريخ أول تفاعل مسجل لدي عبر /id.")


async def bio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bios = [
        "هادئ، لكن حضوري واضح.", "أبني نفسي بصمت.", "الاحترام أسلوب، وليس طلباً.",
        "أتعلم كل يوم شيئاً جديداً.", "لا أبحث عن الكمال، أبحث عن التقدم.",
    ]
    await update.effective_message.reply_text("بايو مقترح:\n\n" + random.choice(bios))


@group_only
async def whisper_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await target_from_reply(update)
    if not target:
        return
    await update.effective_message.reply_text(f"همسة إلى {target.first_name}: أهلاً بك في المجموعة.")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE, arabic_query: str | None = None) -> None:
    if yt_dlp is None:
        await update.effective_message.reply_text("ميزة يوتيوب غير مثبتة. ثبّت المتطلبات ثم أعد التشغيل.")
        return
    query = (arabic_query if arabic_query is not None else " ".join(context.args)).strip()
    if not query:
        await update.effective_message.reply_text("استخدم /search اسم الفيديو")
        return
    status = await update.effective_message.reply_text("أبحث عن النتائج…")
    try:
        def lookup() -> list[str]:
            options = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(f"ytsearch5:{query}", download=False)
                return [f"{i + 1}. {entry.get('title', 'بدون عنوان')}\nhttps://youtu.be/{entry.get('id')}" for i, entry in enumerate(info.get("entries", []))]
        results = await asyncio.to_thread(lookup)
        await status.edit_text("نتائج البحث:\n\n" + ("\n\n".join(results) if results else "لم أجد نتائج."))
    except Exception:
        logger.exception("YouTube search failed")
        await status.edit_text("تعذر البحث الآن. جرّب لاحقاً.")


async def youtube_command(update: Update, context: ContextTypes.DEFAULT_TYPE, arabic_url: str | None = None) -> None:
    if yt_dlp is None:
        await update.effective_message.reply_text("ميزة يوتيوب غير مثبتة. ثبّت المتطلبات ثم أعد التشغيل.")
        return
    url = arabic_url.strip() if arabic_url is not None else (context.args[0] if context.args else "")
    if not url or not re.match(r"https?://", url):
        await update.effective_message.reply_text("استخدم /yt رابط_الفيديو")
        return
    status = await update.effective_message.reply_text("أفحص الفيديو قبل التحميل…")
    temp_dir = tempfile.mkdtemp(prefix="shihab_yt_")
    try:
        def download() -> tuple[str | None, str, int | None]:
            options = {"quiet": True, "no_warnings": True, "format": "best[ext=mp4][height<=720]/best[height<=720]", "outtmpl": os.path.join(temp_dir, "media.%(ext)s"), "noplaylist": True, "max_filesize": 48 * 1024 * 1024}
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "فيديو")
                ydl.process_info(info)
                files = list(Path(temp_dir).glob("media.*"))
                return (str(files[0]) if files else None, title, info.get("filesize") or info.get("filesize_approx"))
        path, title, _ = await asyncio.to_thread(download)
        if not path:
            await status.edit_text("لم أستطع تجهيز الملف أو أنه أكبر من الحد المسموح.")
            return
        await status.edit_text("تم التجهيز، أرسل الملف الآن…")
        with open(path, "rb") as media:
            await update.effective_message.reply_video(video=media, caption=title[:900], supports_streaming=True)
        await status.delete()
    except Exception:
        logger.exception("YouTube download failed")
        await status.edit_text("تعذر تنزيل الفيديو. قد يكون خاصاً أو أكبر من الحد أو غير متاح.")
    finally:
        for child in Path(temp_dir).glob("*"):
            try:
                child.unlink()
            except OSError:
                pass
        try:
            Path(temp_dir).rmdir()
        except OSError:
            pass


async def welcome_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or not message.new_chat_members:
        return
    if not db.feature(chat.id, "welcome"):
        return
    template = db.get_text(chat.id, "welcome") or "أهلاً {name}، نورت المجموعة. اقرأ /rules قبل المشاركة."
    for member in message.new_chat_members:
        text = template.replace("{name}", member.first_name).replace("{username}", f"@{member.username}" if member.username else member.first_name)
        await message.reply_text(text)


async def moderation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user or chat.type == ChatType.PRIVATE:
        return
    db.register(user.id, user.first_name, user.username, chat.id, chat.title or "")
    if user.id != OWNER_ID and db.is_global_banned(user.id):
        try:
            await chat.ban_member(user.id)
            await safe_delete(message)
        except TelegramError:
            logger.debug("Global ban failed for %s", user.id, exc_info=True)
        return
    if await is_admin(update, user.id):
        return
    if db.is_jailed(chat.id, user.id):
        await safe_delete(message)
        return
    until = db.mute_until(chat.id, user.id)
    if until and until > int(datetime.now(timezone.utc).timestamp()):
        await safe_delete(message)
        return
    if until and until <= int(datetime.now(timezone.utc).timestamp()):
        db.clear_mute(chat.id, user.id)
    protection_enabled = db.feature(chat.id, "protection")
    text = message.text or message.caption or ""
    blocked = None
    if message.text and not db.feature(chat.id, "chat"):
        blocked = "الدردشة"
    if protection_enabled and db.feature(chat.id, "antilink") and URL_RE.search(text):
        blocked = "الروابط"
    if protection_enabled and (db.feature(chat.id, "spam") or db.feature(chat.id, "antispam")):
        recent = context.chat_data.setdefault("recent_messages", {})
        stamp = normalize(text)
        previous = recent.get(user.id)
        now = asyncio.get_running_loop().time()
        if stamp and previous and previous[0] == stamp and now - previous[1] < 12:
            blocked = "التكرار"
        recent[user.id] = (stamp, now)
    for feature, predicate in LOCKABLE_MEDIA.items():
        if db.feature(chat.id, feature) is False and predicate(message):
            blocked = FEATURES[feature]
    if message.new_chat_members and db.feature(chat.id, "bot_add") is False:
        blocked = "إضافة الأعضاء"
    if blocked:
        await safe_delete(message)
        if db.feature(chat.id, "warn"):
            count = db.add_warning(chat.id, user.id)
            if count >= 3:
                try:
                    await chat.ban_member(user.id)
                    db.reset_warnings(chat.id, user.id)
                    await message.reply_text(f"تم حظر {user.first_name} بعد 3 مخالفات متتالية.")
                    return
                except TelegramError:
                    pass
        await chat.send_message(f"تم حذف الرسالة بسبب قفل {blocked}.")
        return
    await reply_engine(update, context)


async def reply_engine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat or chat.type == ChatType.PRIVATE or not db.feature(chat.id, "replies"):
        return
    text = normalize(message.text or message.caption or "")
    if not text:
        return
    custom_command = db.command_response(chat.id, text.lstrip("/"))
    if custom_command:
        await message.reply_text(custom_command)
        return
    custom = db.get_reply(chat.id, text)
    if custom:
        await message.reply_text(custom)
        return
    if db.feature(chat.id, "mention") and any(word in text for word in MENTION_WORDS):
        last = context.chat_data.get("last_mention_reply", 0.0)
        now = asyncio.get_running_loop().time()
        if now - last > 20:
            context.chat_data["last_mention_reply"] = now
            await message.reply_text(random.choice(MENTION_REPLIES))
            return
    for keyword, responses in BUILTIN_REPLIES.items():
        if keyword in text and random.random() < 0.65:
            await message.reply_text(random.choice(responses))
            return


async def arabic_unban(update: Update, context: ContextTypes.DEFAULT_TYPE, rest: str) -> None:
    if not await admin_required(update):
        return
    target_id: int | None = None
    for token in reversed(rest.split()):
        if token.isdigit():
            target_id = int(token)
            break
    if target_id is None and update.effective_message.reply_to_message and update.effective_message.reply_to_message.from_user:
        target_id = update.effective_message.reply_to_message.from_user.id
    if target_id is None:
        await update.effective_message.reply_text("استخدم: رفع الحظر بالرد على رسالة العضو أو اكتب رقم المعرف.")
        return
    try:
        await update.effective_chat.unban_member(target_id)
        await update.effective_message.reply_text("تم رفع الحظر.")
    except TelegramError as exc:
        await update.effective_message.reply_text(f"تعذر رفع الحظر: {exc}")


async def natural_language_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    chat = update.effective_chat
    if not message or not message.text or not chat or chat.type == ChatType.PRIVATE:
        return
    raw = normalize(message.text)
    parts = raw.split(maxsplit=1)
    if not parts:
        return
    verb = parts[0]
    rest = parts[1] if len(parts) > 1 else ""

    # الإدارة بالرد على رسالة العضو.
    action_aliases = {
        "طرد": "kick", "اطرد": "kick", "حظر": "ban", "احظر": "ban",
        "كتم": "mute", "اكتم": "mute", "فك الكتم": "unmute", "الغاء الكتم": "unmute", "إلغاء الكتم": "unmute",
        "سجن": "jail", "اسجن": "jail", "فك السجن": "unjail", "الغاء السجن": "unjail", "إلغاء السجن": "unjail",
        "تقييد": "restrict", "قيد": "restrict",
    }
    phrase_action = action_aliases.get(raw)
    chosen_action = phrase_action or action_aliases.get(verb)
    if chosen_action:
        tokens = rest.split() if not phrase_action else []
        duration_args = [token for token in tokens if token.isdigit()][:1] if chosen_action == "mute" else None
        target_tokens = [token for token in tokens if token not in (duration_args or [])]
        target = await target_from_reply(update, target_tokens)
        if target:
            await moderate(update, context, chosen_action, duration_args, target)
        return
    if verb in ("تحذير", "حذر", "حذّر"):
        if not await admin_required(update):
            return
        target = await target_from_reply(update, rest.split())
        if target:
            original_reply = update.effective_message.reply_to_message
            if original_reply:
                await warn_command(update, context)
            else:
                count = db.add_warning(chat.id, target.id)
                await message.reply_text(f"تحذير {target.first_name}: {count}/3")
        return
    if raw in ("التحذيرات", "تحذيرات", "تحذيراته", "عدد التحذيرات"):
        await warns_command(update, context)
        return
    if raw in ("تصفير التحذيرات", "مسح التحذيرات", "الغاء التحذيرات", "إلغاء التحذيرات"):
        await reset_warns_command(update, context)
        return
    if raw in ("لوحة المالك", "لوحة المطور", "لوحة التحكم"):
        await owner_panel(update, context)
        return
    if raw in ("احصائيات البوت", "إحصائيات البوت", "احصائيات"):
        await owner_stats_command(update, context)
        return
    if verb in ("اضافة", "إضافة") and rest.startswith(("مساعد", "مساعد المطور")):
        await owner_assistant_command(update, context, True, rest.split()[-1] if len(rest.split()) > 1 else None)
        return
    if verb in ("ازالة", "إزالة", "حذف") and rest.startswith(("مساعد", "مساعد المطور")):
        await owner_assistant_command(update, context, False, rest.split()[-1] if len(rest.split()) > 1 else None)
        return
    if verb in ("حظر", "منع") and rest.startswith(("عام", "عاماً")):
        tokens = rest.split()
        await global_ban_command(update, context, True, tokens[1] if len(tokens) > 1 else None, " ".join(tokens[2:]) if len(tokens) > 2 else None)
        return
    if verb in ("رفع", "فك", "الغاء", "إلغاء") and rest.startswith(("الحظر العام", "حظر عام")):
        tokens = rest.split()
        await global_ban_command(update, context, False, tokens[-1] if len(tokens) > 2 else None)
        return
    if raw in ("المساعدين", "مساعدين المطور"):
        if await owner_only(update):
            await message.reply_text("مساعدو المطور:\\n" + ("\\n".join(f"• {user_id}" for user_id in db.assistants()) or "لا يوجد"))
        return
    if verb in ("ترقية", "رفع") and rest.startswith(("المجموعة", "القروب")):
        await plan_command(update, context, "vip")
        return
    if verb in ("عادية", "عادي"):
        await plan_command(update, context, "free")
        return
    if verb in ("شحن", "اشحن"):
        days = next((int(token) for token in rest.split() if token.isdigit()), 30)
        await plan_command(update, context, "charge", days)
        return
    if raw in ("فحص الاشتراك", "فحص", "اشتراك المجموعة"):
        await plan_command(update, context, "check")
        return
    if verb in ("رفع", "فك", "الغاء") and "رتبة" in rest:
        rank = rest.split()[-1]
        await set_rank_command(update, context, rank)
        return
    if verb in ("رفع", "ترقية") and ("مشرف" in rest or "ادمن" in rest or "أدمن" in rest):
        await promote_arabic_command(update, context, "manager" if "مدير" in rest else "admin", [token for token in rest.split() if token not in ("مشرف", "ادمن", "أدمن", "مدير")])
        return
    if verb in ("ازالة", "إزالة", "تنزيل", "خفض") and ("مشرف" in rest or "ادمن" in rest or "أدمن" in rest):
        await promote_arabic_command(update, context, "demote", [token for token in rest.split() if token not in ("مشرف", "ادمن", "أدمن")])
        return
    if verb in ("ترقية", "ترقيه"):
        await set_rank_command(update, context, rest.split()[-1] if rest else None)
        return
    if verb in ("رفع", "فك", "الغاء") and ("حظر" in rest or rest.isdigit()):
        await arabic_unban(update, context, rest)
        return
    if raw in ("صلاحياتي", "صلاحياتي هنا", "لقبي", "رتبتي"):
        await permissions_command(update, context)
        return
    if raw in ("صلاحياته", "معلومات العضو", "حالة العضو"):
        await permissions_command(update, context)
        return
    if raw in ("المشرفين", "الادمنية", "الأدمنية", "المدراء", "الادمن"):
        await admins_command(update, context)
        return
    if raw in ("المميزين", "اصحاب الرتب", "أصحاب الرتب"):
        await list_people_command(update, context, "ranked")
        return
    if raw in ("المكتومين", "قائمة المكتومين"):
        await list_people_command(update, context, "muted")
        return
    if raw in ("المسجونين", "قائمة المسجونين"):
        await list_people_command(update, context, "jailed")
        return
    if raw in ("المجموعة", "معلومات المجموعة", "معلومات القروب", "القروب"):
        await group_info_command(update, context)
        return
    if raw in ("الساعة", "الوقت"):
        await date_time_command(update, context)
        return
    if raw in ("التاريخ", "تاريخ اليوم"):
        await date_time_command(update, context, True)
        return
    if raw in ("المطور", "المطورين"):
        await message.reply_text(f"مالك البوت: {OWNER_ID}")
        return

    # القفل والفتح والتفعيل والتعطيل.
    if verb in ("قفل", "فتح", "تفعيل", "تعطيل") and rest:
        if not await admin_required(update):
            return
        key = FEATURE_ALIASES.get(rest, rest)
        if key in FEATURES:
            target_value = verb in ("فتح", "تفعيل")
            if key == "all":
                for feature_name in LOCK_FEATURES:
                    db.set_feature(chat.id, feature_name, target_value)
            else:
                db.set_feature(chat.id, key, target_value)
            label = "فتح" if verb == "فتح" else "قفل" if verb == "قفل" else "تفعيل" if verb == "تفعيل" else "تعطيل"
            await message.reply_text(f"تم {label} {FEATURES[key]}.")
        else:
            await message.reply_text("الميزة غير معروفة. اكتب الإعدادات لرؤية أسماء الميزات.")
        return

    # النصوص والإعدادات.
    if verb in ("تعيين", "حدد", "حدد") and rest:
        setting, _, value = rest.partition(" ")
        if setting in ("الترحيب", "ترحيب"):
            await set_text_command(update, context, "welcome", value)
        elif setting in ("القوانين", "قوانين"):
            await set_text_command(update, context, "rules", value)
        return
    if raw in ("حذف الترحيب", "مسح الترحيب"):
        await delete_text_command(update, context, "welcome")
        return
    if raw in ("حذف القوانين", "مسح القوانين"):
        await delete_text_command(update, context, "rules")
        return

    # الردود والأوامر المخصصة.
    if verb in ("اضف", "أضف") and rest.startswith("رد"):
        await add_reply_command(update, context, rest[2:].strip())
        return
    if verb in ("مسح", "احذف") and rest.startswith("رد "):
        await del_reply_command(update, context, rest[4:].strip())
        return
    if raw in ("مسح الردود", "حذف الردود"):
        await del_all_replies_command(update, context)
        return

    # البحث والخدمات.
    if verb in ("بحث", "ابحث"):
        await search_command(update, context, rest)
        return
    if verb in ("يوت", "يوتيوب", "تحميل"):
        await youtube_command(update, context, rest)
        return
    if raw in ("الاوامر", "الأوامر", "مساعدة"):
        await help_command(update, context)
    elif raw in ("الخدمات", "خدمات"):
        await services_command(update, context)
    elif raw in ("الاعدادات", "الإعدادات", "الاعدادات"):
        await settings_command(update, context)
    elif raw in ("القوانين", "قوانين"):
        await show_rules(update, context)
    elif raw in ("معلوماتي", "ايدي", "آيدي", "معرفي"):
        await identity_command(update, context)
    elif raw in ("عمري", "عمر الحساب"):
        await age_command(update, context)
    elif raw in ("بايو", "بايو عشوائي"):
        await bio_command(update, context)
    elif raw == "خدماتي":
        await services_command(update, context)


async def owner_only(update: Update) -> bool:
    if not update.effective_user or update.effective_user.id != OWNER_ID or OWNER_ID == 0:
        if update.effective_message:
            await update.effective_message.reply_text("هذا القسم متاح لمالك البوت فقط.")
        return False
    return True


async def owner_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await owner_only(update):
        return
    stats = db.stats()
    plans = db.plan_counts()
    await update.effective_message.reply_text(
        f"لوحة مالك شهاب\\n\\nالمستخدمون: {stats['users']}\\nالمجموعات: {stats['groups']}\\nVIP: {plans.get('vip', 0)}\\nعادية: {plans.get('free', 0)}\\nالمساعدون: {len(db.assistants())}\\nالحظر العام: {len(db.global_bans())}\\nالأحداث المسجلة: {stats['events']}\\n\\nالأوامر العربية: مساعد المطور، حظر عام، ترقية المجموعة، شحن 30، فحص الاشتراك، بث نص.\\nلا أضع إعادة تشغيل خطرة داخل الدردشة؛ أعد تشغيل الخدمة من مدير التشغيل.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("تحديث", callback_data="owner:home")]]),
    )


async def owner_target_id(update: Update, identifier: str | None = None) -> int | None:
    if update.effective_message.reply_to_message and update.effective_message.reply_to_message.from_user:
        return update.effective_message.reply_to_message.from_user.id
    if identifier:
        row = db.find_user(identifier)
        if row:
            return int(row["user_id"])
        if identifier.isdigit():
            return int(identifier)
    return None


async def owner_assistant_command(update: Update, context: ContextTypes.DEFAULT_TYPE, enabled: bool, arabic_identifier: str | None = None) -> None:
    if not await owner_only(update):
        return
    target_id = await owner_target_id(update, arabic_identifier or (context.args[0] if context.args else None))
    if not target_id:
        await update.effective_message.reply_text("استخدم: اضافة مساعد 123456 أو بالرد على رسالة المستخدم.")
        return
    db.set_assistant(target_id, enabled)
    await update.effective_message.reply_text(f"تم {'إضافة' if enabled else 'إزالة'} مساعد المطور: {target_id}.")


async def global_ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE, enabled: bool, arabic_identifier: str | None = None, arabic_reason: str | None = None) -> None:
    if not await owner_only(update):
        return
    target_id = await owner_target_id(update, arabic_identifier or (context.args[0] if context.args else None))
    if not target_id:
        await update.effective_message.reply_text("استخدم: حظر عام 123456 أو بالرد على رسالة المستخدم.")
        return
    reason = arabic_reason or (" ".join(context.args[1:]) if len(context.args) > 1 else None)
    db.set_global_ban(target_id, reason, enabled)
    await update.effective_message.reply_text(f"تم {'الحظر العام' if enabled else 'رفع الحظر العام'} للمعرف {target_id}.")


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str, days: int | None = None) -> None:
    if not await owner_only(update):
        return
    chat = update.effective_chat
    if not chat or chat.type == ChatType.PRIVATE:
        await update.effective_message.reply_text("استخدم هذا الأمر داخل المجموعة المطلوبة.")
        return
    actor = update.effective_user.id
    if mode == "vip":
        db.set_plan(chat.id, "vip", None, actor)
        text = "تم ترقية المجموعة إلى VIP بلا تاريخ انتهاء محدد."
    elif mode == "free":
        db.set_plan(chat.id, "free", None, actor)
        text = "تم إرجاع المجموعة إلى الخطة العادية."
    elif mode == "charge":
        days = days or 30
        expires = db.charge_plan(chat.id, days, actor)
        text = f"تم شحن المجموعة {days} يوماً. الانتهاء: {datetime.fromtimestamp(expires).strftime('%Y-%m-%d')}"
    else:
        plan, expires = db.plan_info(chat.id)
        remaining = max(0, int((expires - datetime.now(timezone.utc).timestamp()) / 86400)) if expires else "غير محدد"
        text = f"خطة المجموعة: {plan}\nالأيام المتبقية: {remaining}"
    db.log(chat.id, actor, f"plan:{mode}")
    await update.effective_message.reply_text(text)


async def owner_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await owner_only(update):
        return
    stats = db.stats()
    plans = db.plan_counts()
    await update.effective_message.reply_text(f"إحصائيات شهاب\\n\\nالمستخدمون: {stats['users']}\\nالمجموعات: {stats['groups']}\\nVIP: {plans.get('vip', 0)}\\nعادية: {plans.get('free', 0)}\\nالمساعدون: {len(db.assistants())}\\nالمحظورون عاماً: {len(db.global_bans())}\\nالأحداث: {stats['events']}")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await owner_only(update):
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text("استخدم /broadcast نص الرسالة")
        return
    sent = 0
    for user_id in db.user_ids():
        try:
            await context.bot.send_message(user_id, text)
            sent += 1
            await asyncio.sleep(0.05)
        except (Forbidden, BadRequest):
            continue
        except TelegramError:
            logger.debug("Broadcast failed for %s", user_id, exc_info=True)
    await update.effective_message.reply_text(f"اكتمل البث. تم الإرسال إلى {sent} مستخدم.")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    data = query.data or ""
    user_id = query.from_user.id
    if data == "home:commands":
        await query.edit_message_text(commands_text(), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="home:main")]]))
    elif data == "home:services":
        await query.edit_message_text(services_text(), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="home:main")]]))
    elif data == "home:about":
        await query.edit_message_text("شهاب ليس مجرد ردود عشوائية: هو نظام إدارة بصلاحيات، إعدادات مستقلة لكل مجموعة، وسجل للأحداث مع حماية من الأخطاء الشائعة.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="home:main")]]))
    elif data == "home:main":
        await query.edit_message_text("القائمة الرئيسية لشهاب:", reply_markup=main_keyboard(user_id == OWNER_ID))
    elif data == "home:settings":
        chat = update.effective_chat
        if not chat or chat.type == ChatType.PRIVATE:
            await query.edit_message_text("افتح الإعدادات من داخل المجموعة التي تريد إدارتها.")
            return
        features = db.all_features(chat.id)
        lines = ["إعدادات المجموعة الحالية:"] + [f"{'مفتوح' if features.get(k, True) else 'مغلق'} — {v}" for k, v in FEATURES.items()]
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="home:main")]]))
    elif data == "owner:home":
        if user_id != OWNER_ID:
            await query.edit_message_text("غير مصرح.")
            return
        stats = db.stats()
        await query.edit_message_text(f"لوحة المالك\n\nالمستخدمون: {stats['users']}\nالمجموعات: {stats['groups']}\nالأحداث: {stats['events']}\n\nاستخدم /broadcast نص للبث.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="home:main")]]))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled update error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("حدث خطأ مؤقت، سجّلت المشكلة وسأتابع العمل.")
        except TelegramError:
            pass


def add_handlers(app: Application) -> None:
    app.add_handler(CommandHandler(["start", "menu"], command_start))
    app.add_handler(CommandHandler(["help"], help_command))
    app.add_handler(CommandHandler(["services"], services_command))
    app.add_handler(CommandHandler(["settings"], settings_command))
    app.add_handler(CommandHandler(["kick"], lambda u, c: moderate(u, c, "kick")))
    app.add_handler(CommandHandler(["ban"], lambda u, c: moderate(u, c, "ban")))
    app.add_handler(CommandHandler(["unban"], unban_command))
    app.add_handler(CommandHandler(["mute"], lambda u, c: moderate(u, c, "mute")))
    app.add_handler(CommandHandler(["unmute"], lambda u, c: moderate(u, c, "unmute")))
    app.add_handler(CommandHandler(["jail"], lambda u, c: moderate(u, c, "jail")))
    app.add_handler(CommandHandler(["unjail"], lambda u, c: moderate(u, c, "unjail")))
    app.add_handler(CommandHandler(["restrict"], lambda u, c: moderate(u, c, "restrict")))
    app.add_handler(CommandHandler(["warn"], warn_command))
    app.add_handler(CommandHandler(["warns"], warns_command))
    app.add_handler(CommandHandler(["resetwarns"], reset_warns_command))
    app.add_handler(CommandHandler(["setwelcome"], lambda u, c: set_text_command(u, c, "welcome")))
    app.add_handler(CommandHandler(["delwelcome"], lambda u, c: delete_text_command(u, c, "welcome")))
    app.add_handler(CommandHandler(["setrules"], lambda u, c: set_text_command(u, c, "rules")))
    app.add_handler(CommandHandler(["rules"], show_rules))
    app.add_handler(CommandHandler(["lock"], lambda u, c: lock_command(u, c, False)))
    app.add_handler(CommandHandler(["unlock"], lambda u, c: lock_command(u, c, True)))
    app.add_handler(CommandHandler(["enable"], lambda u, c: toggle_command(u, c, True)))
    app.add_handler(CommandHandler(["disable"], lambda u, c: toggle_command(u, c, False)))
    app.add_handler(CommandHandler(["addreply"], add_reply_command))
    app.add_handler(CommandHandler(["replies"], replies_command))
    app.add_handler(CommandHandler(["delreply"], del_reply_command))
    app.add_handler(CommandHandler(["delallreplies"], del_all_replies_command))
    app.add_handler(CommandHandler(["addcmd"], add_command_command))
    app.add_handler(CommandHandler(["delcmd"], del_command_command))
    app.add_handler(CommandHandler(["id"], identity_command))
    app.add_handler(CommandHandler(["age"], age_command))
    app.add_handler(CommandHandler(["bio"], bio_command))
    app.add_handler(CommandHandler(["whisper"], whisper_command))
    app.add_handler(CommandHandler(["search"], search_command))
    app.add_handler(CommandHandler(["yt"], youtube_command))
    app.add_handler(CommandHandler(["owner", "panel"], owner_panel))
    app.add_handler(CommandHandler(["broadcast"], broadcast_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_handler), group=0)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, moderation_handler), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, natural_language_handler), group=2)


def build_app() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN غير موجود في ملف .env")
    if OWNER_ID <= 0:
        raise RuntimeError("OWNER_ID غير صحيح في ملف .env")
    app = Application.builder().token(BOT_TOKEN).build()
    add_handlers(app)
    app.add_error_handler(error_handler)
    return app


if __name__ == "__main__":
    try:
        application = build_app()
        logger.info("بوت شهاب جاهز للعمل")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("تم إيقاف البوت")
    except Exception as exc:
        logger.error("تعذر تشغيل البوت: %s", exc)
        raise
