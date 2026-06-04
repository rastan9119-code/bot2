import os
import re
import sqlite3
from datetime import datetime, timedelta

# Create folders before importing logger / other modules that write files.
os.makedirs("data", exist_ok=True)
os.makedirs("data/backup", exist_ok=True)
os.makedirs("logs", exist_ok=True)

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import (
    BOT_TOKEN as CONFIG_BOT_TOKEN,
    OWNER_ID,
    WELCOME_TEXT,
    DEFAULT_FEATURES,
    DATABASE_NAME,
)
from database import get_connection, init_database

from users import (
    add_user,
    update_last_seen,
    get_user,
    get_all_users,
    count_users,
    count_today_users,
    ban_user,
    unban_user,
    is_banned,
)

from roles import (
    set_owner,
    set_temp_owner,
    set_vpn_admin,
    set_music_admin,
    set_support_admin,
    clear_all_roles,
    get_roles,
    is_owner,
    is_temp_owner,
    is_vpn_admin,
    is_music_admin,
    is_support_admin,
    has_any_admin_role,
)
from owner import get_admins as owner_get_admins

from music import (
    add_song,
    delete_song,
    set_song_active,
    update_song,
    get_song,
    get_all_songs,
    get_new_songs,
    get_top_songs,
    search_song,
    get_category_songs,
    get_categories,
    get_random_song,
    get_random_song_by_category,
    increase_download,
    add_song_score,
    get_song_stats,
)

from support import (
    create_ticket,
    create_complaint,
    get_open_tickets,
    get_open_complaints,
    get_ticket,
    get_replies,
    close_ticket,
    close_complaint,
    save_reply,
)

from vpn import (
    add_plan,
    get_plans,
    get_plan,
    add_server,
    get_servers,
    get_server,
    assign_server,
    get_user_servers,
    add_test_server,
    get_test_server,
    user_received_test,
    mark_test_received,
)

from wallet import (
    ensure_wallet,
    get_balance,
    add_balance,
    subtract_balance,
    get_wallet_transactions,
    format_balance,
)

from payments import (
    create_payment,
    get_pending_payments,
    get_payment,
    approve_payment,
    reject_payment,
)

from stats import get_stats
from menus import (
    main_menu,
    music_menu,
    vpn_menu,
    wallet_menu,
    owner_menu,
)
from admin_panel import admin_keyboard

from settings import get_setting, set_setting
from logger import log_info, log_error


TOKEN = (os.getenv("BOT_TOKEN") or CONFIG_BOT_TOKEN or "").strip()

MUSIC_GENRES = [
    "پاپ",
    "رپ فارسی",
    "هیپ هاپ",
    "سنتی",
    "الکترونیک",
    "ترنس",
    "هاوس",
    "راک",
    "متال",
    "کلاسیک",
    "بی‌کلام",
    "شاد",
]

PAGE_SIZE_SONGS = 8
PAGE_SIZE_PLANS = 5

DEFAULT_CARD_NUMBER = "bank_card_number"
DEFAULT_CARD_HOLDER = "bank_card_holder"

FLOW_STATE = "state"


# =============================
# Compatibility bootstrap
# =============================

def _table_columns(table_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    rows = cur.fetchall()
    conn.close()
    return [r[1] for r in rows]


def _table_exists(table_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table_name,),
    )
    row = cur.fetchone()
    conn.close()
    return row is not None


def _add_column_if_missing(table_name, column_name, column_def):
    if not _table_exists(table_name):
        return

    cols = _table_columns(table_name)
    if column_name not in cols:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_def}")
        conn.commit()
        conn.close()


def ensure_compat_schema():
    # Tables used by payments.py / support.py / vpn.py
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            receipt_file_id TEXT,
            status TEXT DEFAULT 'pending',
            reviewed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS replies(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            admin_id INTEGER,
            message TEXT,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vpn_plans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            volume TEXT,
            duration TEXT,
            price INTEGER,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vpn_servers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER,
            server_name TEXT,
            location TEXT,
            config_text TEXT,
            is_used INTEGER DEFAULT 0,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_vpn(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            server_id INTEGER,
            assigned_at TEXT,
            expire_date TEXT,
            status TEXT DEFAULT 'active'
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vpn_test(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_text TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vpn_test_users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            received_at TEXT
        )
        """
    )

    conn.commit()
    conn.close()

    # Add columns missing in older tables.
    _add_column_if_missing("tickets", "username", "username TEXT")
    _add_column_if_missing("complaints", "username", "username TEXT")
    _add_column_if_missing("tickets", "admin_reply", "admin_reply TEXT")
    _add_column_if_missing("complaints", "admin_reply", "admin_reply TEXT")

    # Default settings
    if get_setting("welcome_text") is None:
        set_setting("welcome_text", WELCOME_TEXT.strip())

    if get_setting(DEFAULT_CARD_NUMBER) is None:
        set_setting(DEFAULT_CARD_NUMBER, "")

    if get_setting(DEFAULT_CARD_HOLDER) is None:
        set_setting(DEFAULT_CARD_HOLDER, "")

    # Feature flags
    for name, enabled in DEFAULT_FEATURES.items():
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO feature_flags
            (name, is_enabled, note, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (name, 1 if enabled else 0, "default", now()),
        )
        conn.commit()
        conn.close()


def bootstrap_owner():
    try:
        set_owner(OWNER_ID, True)
    except Exception:
        pass


# =============================
# Utilities
# =============================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_username(user):
    if not user:
        return ""
    return f"@{user.username}" if user.username else ""


def user_label(user):
    if not user:
        return "unknown"
    if user.username:
        return f"@{user.username}"
    return user.full_name or str(user.id)


def log_activity(telegram_id, action, details=""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO activity_logs
        (telegram_id, action, details, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (telegram_id, action, details, now()),
    )
    conn.commit()
    conn.close()


def is_feature_enabled(name, default=True):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT is_enabled
        FROM feature_flags
        WHERE name = ?
        """,
        (name,),
    )
    row = cur.fetchone()
    conn.close()
    if row is None:
        return default
    return bool(row[0])


def set_feature_enabled(name, enabled, note=""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO feature_flags
        (name, is_enabled, note, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            is_enabled=excluded.is_enabled,
            note=excluded.note,
            updated_at=excluded.updated_at
        """,
        (name, 1 if enabled else 0, note, now()),
    )
    conn.commit()
    conn.close()


def parse_int(text, default=None):
    try:
        return int(str(text).strip())
    except Exception:
        return default


def parse_duration_days(duration_text):
    t = (duration_text or "").strip()
    if not t:
        return 30

    m = re.search(r"(\d+)", t)
    if not m:
        return 30

    n = int(m.group(1))
    if "ماه" in t:
        return max(1, n * 30)
    if "هفته" in t:
        return max(1, n * 7)
    return max(1, n)


def file_kind_and_id(raw):
    if not raw:
        return "audio", ""
    if ":" in raw:
        k, v = raw.split(":", 1)
        if k in {"audio", "document", "photo"}:
            return k, v
    return "audio", raw


def store_media(kind, file_id):
    return f"{kind}:{file_id}"


def get_feature_text():
    rows = []
    for key in sorted(DEFAULT_FEATURES.keys()):
        status = "✅ فعال" if is_feature_enabled(key) else "⛔ غیرفعال"
        rows.append(f"{key}: {status}")
    return "\n".join(rows)


def admin_ids_unique():
    ids = {OWNER_ID}
    for uid, _role in owner_get_admins():
        ids.add(int(uid))
    # main owner/temp owners that may not appear in owner_get_admins
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT telegram_id
        FROM roles
        WHERE is_owner = 1 OR is_temp_owner = 1
        """
    )
    for (uid,) in cur.fetchall():
        ids.add(int(uid))
    conn.close()
    return sorted(ids)


def notify_admins(context, text):
    for admin_id in admin_ids_unique():
        try:
            context.bot.send_message(chat_id=admin_id, text=text)
        except Exception:
            pass


def has_owner_panel_access(user_id):
    return is_owner(user_id) or is_temp_owner(user_id) or int(user_id) == int(OWNER_ID)


def has_admin_access(user_id):
    return (
        is_owner(user_id)
        or is_temp_owner(user_id)
        or is_vpn_admin(user_id)
        or is_music_admin(user_id)
        or is_support_admin(user_id)
        or int(user_id) == int(OWNER_ID)
    )


def ensure_wallet_row(user_id):
    try:
        ensure_wallet(user_id)
    except Exception:
        pass


def calc_expire_date(duration_text):
    days = parse_duration_days(duration_text)
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def get_payment_card_info():
    number = (get_setting(DEFAULT_CARD_NUMBER) or "").strip()
    holder = (get_setting(DEFAULT_CARD_HOLDER) or "").strip()
    return number, holder


# =============================
# Flow helpers
# =============================

def set_flow(context, state, **data):
    context.user_data["flow"] = {"state": state, **data}


def get_flow(context):
    return context.user_data.get("flow", {})


def clear_flow(context):
    context.user_data.pop("flow", None)


# =============================
# Song list rendering
# =============================

def song_caption(song):
    song_id, title, file_id, category, score, downloads, is_active, created_at = song
    return (
        f"🎵 {title}\n"
        f"📂 دسته‌بندی: {category}\n"
        f"⭐ امتیاز: {float(score):.1f}\n"
        f"⬇️ دانلود: {downloads}"
    )


def build_song_keyboard(songs, page, mode):
    total = len(songs)
    start = page * PAGE_SIZE_SONGS
    end = start + PAGE_SIZE_SONGS
    page_songs = songs[start:end]

    keyboard = []
    for song in page_songs:
        song_id, title, file_id, category, score, downloads, is_active, created_at = song
        text = f"{title} | ⭐ {float(score):.1f} | ⬇️ {downloads}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"song_open:{song_id}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data="songpage:prev"))
    if end < total:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data="songpage:next"))
    if nav:
        keyboard.append(nav)

    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="songback:main")])
    return InlineKeyboardMarkup(keyboard), page_songs, total


async def show_song_list(message, context, songs, title, mode, page=0):
    context.user_data["song_view"] = {
        "mode": mode,
        "page": page,
        "query": context.user_data.get("song_view", {}).get("query", ""),
        "category": context.user_data.get("song_view", {}).get("category", ""),
        "results": songs if mode == "search" else None,
    }
    markup, _, total = build_song_keyboard(songs, page, mode)
    start = page * PAGE_SIZE_SONGS
    end = min(start + PAGE_SIZE_SONGS, total)
    text = f"{title}\n\nنمایش {start + 1 if total else 0} تا {end} از {total}"
    await message.reply_text(text, reply_markup=markup)


async def edit_song_list(query, context, songs, title, mode, page=0):
    context.user_data["song_view"] = {
        "mode": mode,
        "page": page,
        "query": context.user_data.get("song_view", {}).get("query", ""),
        "category": context.user_data.get("song_view", {}).get("category", ""),
        "results": songs if mode == "search" else None,
    }
    markup, _, total = build_song_keyboard(songs, page, mode)
    start = page * PAGE_SIZE_SONGS
    end = min(start + PAGE_SIZE_SONGS, total)
    text = f"{title}\n\nنمایش {start + 1 if total else 0} تا {end} از {total}"
    await query.edit_message_text(text, reply_markup=markup)


def resolve_song_list(flow):
    mode = flow.get("mode")
    if mode == "all":
        return get_all_songs()
    if mode == "new":
        return get_new_songs(50)
    if mode == "top":
        return get_top_songs(50)
    if mode == "search":
        return flow.get("results", []) or []
    if mode == "category":
        cat = flow.get("category")
        return get_category_songs(cat) if cat else []
    return []


def build_category_keyboard(prefix="randcat"):
    cats = get_categories()
    if not cats:
        cats = MUSIC_GENRES[:]

    keyboard = []
    row = []
    for idx, cat in enumerate(cats, start=1):
        row.append(InlineKeyboardButton(cat, callback_data=f"{prefix}:{cat}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="randback:music")])
    return InlineKeyboardMarkup(keyboard)


def build_rating_keyboard(song_id):
    keyboard = [
        [
            InlineKeyboardButton("⭐1", callback_data=f"rate:{song_id}:1"),
            InlineKeyboardButton("⭐2", callback_data=f"rate:{song_id}:2"),
            InlineKeyboardButton("⭐3", callback_data=f"rate:{song_id}:3"),
            InlineKeyboardButton("⭐4", callback_data=f"rate:{song_id}:4"),
            InlineKeyboardButton("⭐5", callback_data=f"rate:{song_id}:5"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# =============================
# Plan / server rendering
# =============================

def plan_caption(plan):
    plan_id, title, volume, duration, price, created_at = plan
    return (
        f"💳 {title}\n"
        f"📦 حجم: {volume}\n"
        f"⏳ مدت: {duration}\n"
        f"💰 قیمت: {price:,} تومان"
    )


def build_plan_keyboard(plans, page):
    total = len(plans)
    start = page * PAGE_SIZE_PLANS
    end = start + PAGE_SIZE_PLANS
    page_plans = plans[start:end]

    keyboard = []
    for plan in page_plans:
        plan_id, title, volume, duration, price, created_at = plan
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{title} | {price:,} تومان",
                    callback_data=f"plan_open:{plan_id}",
                )
            ]
        )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data="planpage:prev"))
    if end < total:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data="planpage:next"))
    if nav:
        keyboard.append(nav)

    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="planback:main")])
    return InlineKeyboardMarkup(keyboard), page_plans, total


async def show_plan_list(message, context, plans, title, page=0):
    context.user_data["plan_view"] = {"page": page}
    markup, _, total = build_plan_keyboard(plans, page)
    start = page * PAGE_SIZE_PLANS
    end = min(start + PAGE_SIZE_PLANS, total)
    text = f"{title}\n\nنمایش {start + 1 if total else 0} تا {end} از {total}"
    await message.reply_text(text, reply_markup=markup)


async def edit_plan_list(query, context, plans, title, page=0):
    context.user_data["plan_view"] = {"page": page}
    markup, _, total = build_plan_keyboard(plans, page)
    start = page * PAGE_SIZE_PLANS
    end = min(start + PAGE_SIZE_PLANS, total)
    text = f"{title}\n\nنمایش {start + 1 if total else 0} تا {end} از {total}"
    await query.edit_message_text(text, reply_markup=markup)


def build_server_keyboard(server_id, back_plan_id):
    keyboard = [
        [
            InlineKeyboardButton("💰 پرداخت از کیف پول", callback_data=f"server_pay_wallet:{server_id}"),
            InlineKeyboardButton("💳 پرداخت مستقیم", callback_data=f"server_pay_direct:{server_id}"),
        ],
        [InlineKeyboardButton("🔙 بازگشت به پلن", callback_data=f"plan_open:{back_plan_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def server_caption(server, plan):
    server_id, plan_id, server_name, location, config_text, is_used, created_at = server
    _, title, volume, duration, price, _ = plan
    return (
        f"🌐 سرور: {server_name}\n"
        f"📍 لوکیشن: {location}\n"
        f"📦 پلن: {title}\n"
        f"⏳ مدت: {duration}\n"
        f"💰 قیمت: {price:,} تومان\n"
        f"وضعیت: {'استفاده شده' if is_used else 'آماده'}"
    )


# =============================
# Media helpers
# =============================

async def send_song_media(chat, context, song):
    song_id, title, file_id, category, score, downloads, is_active, created_at = song
    kind, raw_id = file_kind_and_id(file_id)
    caption = song_caption(song)

    if kind == "document":
        await context.bot.send_document(
            chat_id=chat.id,
            document=raw_id,
            caption=caption,
            reply_markup=build_rating_keyboard(song_id),
        )
    else:
        await context.bot.send_audio(
            chat_id=chat.id,
            audio=raw_id,
            caption=caption,
            reply_markup=build_rating_keyboard(song_id),
        )
    increase_download(song_id)


async def send_receipt_to_admin(chat_id, context, payment):
    pay_id, user_id, amount, receipt_file_id, status, reviewed_at, created_at = payment
    kind, raw_id = file_kind_and_id(receipt_file_id)
    caption = (
        f"💳 پرداخت جدید #{pay_id}\n"
        f"کاربر: {user_id}\n"
        f"مبلغ: {amount:,} تومان\n"
        f"وضعیت: {status}\n"
        f"زمان: {created_at}"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ تایید", callback_data=f"pay_approve:{pay_id}"),
                InlineKeyboardButton("❌ رد", callback_data=f"pay_reject:{pay_id}"),
            ]
        ]
    )

    try:
        if kind == "photo":
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=raw_id,
                caption=caption,
                reply_markup=keyboard,
            )
        else:
            await context.bot.send_document(
                chat_id=chat_id,
                document=raw_id,
                caption=caption,
                reply_markup=keyboard,
            )
    except Exception:
        await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=keyboard,
        )


async def send_test_server_to_user(update, context):
    test_server = get_test_server()
    user = update.effective_user

    if not test_server:
        await update.message.reply_text("🧪 سرور تست فعلاً فعال نیست.")
        return

    if user_received_test(user.id):
        await update.message.reply_text("⚠️ شما قبلاً سرور تست دریافت کرده‌اید.")
        return

    _, config_text, is_active, created_at = test_server
    mark_test_received(user.id)
    await update.message.reply_text(
        "🧪 سرور تست شما:\n\n"
        f"{config_text}\n\n"
        "این سرور فقط یک‌بار برای هر کاربر قابل دریافت است."
    )


# =============================
# Command handlers
# =============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_banned(user.id):
        await update.message.reply_text("⛔ حساب شما مسدود است.")
        return

    add_user(user.id, user.username, user.full_name)
    update_last_seen(user.id)
    ensure_wallet_row(user.id)
    clear_flow(context)

    log_activity(user.id, "start", "user started bot")

    await update.message.reply_text(
        get_setting("welcome_text") or WELCOME_TEXT,
        reply_markup=main_menu(),
    )


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    clear_flow(context)
    await update.message.reply_text("منوی اصلی:", reply_markup=main_menu())


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    clear_flow(context)

    if has_owner_panel_access(user.id):
        await update.message.reply_text(
            "👮 پنل مالک / مدیر\n\n"
            "دستورات سریع:\n"
            "/admins\n"
            "/addadmin <id> <roles>\n"
            "/removeadmin <id>\n"
            "/setcard <number> | <holder>\n"
            "/feature <name> on/off",
            reply_markup=owner_menu(),
        )
    else:
        await update.message.reply_text(
            "👮 پنل ادمین\n\n"
            "دستورات سریع:\n"
            "/stats\n"
            "/pendingpayments\n"
            "/tickets\n"
            "/addsong\n"
            "/addplan\n"
            "/addserver",
            reply_markup=admin_keyboard(),
        )


async def owner_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_owner_panel_access(user.id):
        return

    clear_flow(context)
    await update.message.reply_text(
        "👑 پنل مالک\n\n"
        "مدیریت ادمین‌ها، پیام همگانی، تنظیمات و آمار.",
        reply_markup=owner_menu(),
    )


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    try:
        s = get_stats()
        song_stats = get_song_stats()
        admins = admin_ids_unique()

        text = (
            "📊 آمار کلی\n\n"
            f"👥 کاربران کل: {s.get('users', 0)}\n"
            f"📅 کاربران امروز: {s.get('today_users', 0)}\n"
            f"🎵 آهنگ‌ها: {s.get('songs', 0)}\n"
            f"⬇️ دانلودها: {song_stats.get('downloads', 0)}\n"
            f"⭐ میانگین امتیاز: {song_stats.get('avg_score', 0.0):.1f}\n"
            f"🎫 تیکت‌ها: {s.get('tickets', 0)}\n"
            f"💳 پرداخت‌ها: {s.get('payments', 0)}\n"
            f"🌐 پلن‌ها: {s.get('vpn_plans', 0)}\n"
            f"🖥 سرورها: {s.get('vpn_servers', 0)}\n"
            f"👮 ادمین‌ها: {len(admins)}\n"
            f"👛 مجموع کیف پول: {s.get('wallet_total', 0):,} تومان"
        )
        await update.message.reply_text(text)
    except Exception as e:
        log_error(e)
        await update.message.reply_text("❌ خطا در دریافت آمار.")


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_owner_panel_access(user.id):
        return

    text = " ".join(context.args).strip()
    if text:
        sent = 0
        for u in get_all_users():
            uid = int(u[1])
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(f"✅ پیام برای {sent} کاربر ارسال شد.")
        return

    set_flow(context, "broadcast_wait")
    await update.message.reply_text("متن پیام همگانی را ارسال کنید.")


async def addadmin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_owner_panel_access(user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "نمونه:\n"
            "/addadmin 123456 vpn music support temp"
        )
        return

    target_id = parse_int(context.args[0])
    if not target_id:
        await update.message.reply_text("آیدی نامعتبر است.")
        return

    roles_requested = {arg.lower() for arg in context.args[1:]}
    if "temp" in roles_requested or "temp_owner" in roles_requested:
        set_temp_owner(target_id, True)
    if "vpn" in roles_requested or "vpn_admin" in roles_requested:
        set_vpn_admin(target_id, True)
    if "music" in roles_requested or "music_admin" in roles_requested:
        set_music_admin(target_id, True)
    if "support" in roles_requested or "support_admin" in roles_requested:
        set_support_admin(target_id, True)

    await update.message.reply_text(f"✅ نقش‌ها برای {target_id} ثبت شد.")


async def removeadmin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_owner_panel_access(user.id):
        return

    if not context.args:
        await update.message.reply_text("نمونه:\n/removeadmin 123456")
        return

    target_id = parse_int(context.args[0])
    if not target_id:
        await update.message.reply_text("آیدی نامعتبر است.")
        return

    clear_all_roles(target_id)
    await update.message.reply_text(f"✅ تمام نقش‌ها برای {target_id} حذف شد.")


async def admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_owner_panel_access(user.id):
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT telegram_id, is_owner, is_temp_owner, is_vpn_admin, is_music_admin, is_support_admin
        FROM roles
        ORDER BY telegram_id ASC
        """
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("هیچ نقشی ثبت نشده است.")
        return

    lines = ["👮 فهرست نقش‌ها:\n"]
    for row in rows:
        uid, owner_v, temp_v, vpn_v, music_v, support_v = row
        roles = []
        if owner_v:
            roles.append("OWNER")
        if temp_v:
            roles.append("TEMP")
        if vpn_v:
            roles.append("VPN")
        if music_v:
            roles.append("MUSIC")
        if support_v:
            roles.append("SUPPORT")
        lines.append(f"{uid}: {', '.join(roles) if roles else 'USER'}")
    await update.message.reply_text("\n".join(lines))


async def setcard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_owner_panel_access(user.id):
        return

    raw = " ".join(context.args).strip()
    if not raw:
        await update.message.reply_text(
            "نمونه:\n"
            "/setcard 6037-xxxx-xxxx-xxxx | نام صاحب کارت"
        )
        return

    if "|" not in raw:
        await update.message.reply_text("فرمت درست نیست. از | استفاده کنید.")
        return

    number, holder = [x.strip() for x in raw.split("|", 1)]
    set_setting(DEFAULT_CARD_NUMBER, number)
    set_setting(DEFAULT_CARD_HOLDER, holder)
    await update.message.reply_text("✅ اطلاعات کارت ذخیره شد.")


async def feature_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_owner_panel_access(user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "نمونه:\n"
            "/feature music_enabled off\n"
            "/feature vpn_enabled on"
        )
        return

    name = context.args[0].strip()
    value = context.args[1].strip().lower()
    enabled = value in {"on", "1", "true", "yes", "enable", "enabled"}
    set_feature_enabled(name, enabled, "owner toggle")
    await update.message.reply_text(
        f"✅ {name} = {'on' if enabled else 'off'}"
    )


async def setwelcome_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_owner_panel_access(user.id):
        return

    text = " ".join(context.args).strip()
    if text:
        set_setting("welcome_text", text)
        await update.message.reply_text("✅ متن خوش‌آمد ذخیره شد.")
        return

    set_flow(context, "set_welcome_wait")
    await update.message.reply_text("متن خوش‌آمد جدید را ارسال کنید.")


async def pendingpayments_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    rows = get_pending_payments()
    if not rows:
        await update.message.reply_text("پرداخت معلقی وجود ندارد.")
        return

    lines = ["💳 پرداخت‌های معلق:\n"]
    keyboard = []
    for row in rows[:20]:
        pay_id, uid, amount, receipt_file_id, status, reviewed_at, created_at = row
        lines.append(f"#{pay_id} | کاربر {uid} | {amount:,} تومان")
        keyboard.append([InlineKeyboardButton(f"پرداخت #{pay_id}", callback_data=f"pay_open:{pay_id}")])

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def orders_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, user_id, plan_id, server_id, amount, payment_method, status, admin_note, created_at
        FROM orders
        WHERE status = 'pending'
        ORDER BY id DESC
        """
    )
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("سفارشی در انتظار بررسی نیست.")
        return

    lines = ["🛒 سفارش‌های معلق:\n"]
    for row in rows[:20]:
        oid, uid, plan_id, server_id, amount, method, status, admin_note, created_at = row
        lines.append(f"#{oid} | کاربر {uid} | پلن {plan_id} | {amount:,} | {method}")

    await update.message.reply_text("\n".join(lines))


async def approveorder_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    if len(context.args) < 1:
        await update.message.reply_text("نمونه:\n/approveorder 12")
        return

    order_id = parse_int(context.args[0])
    if not order_id:
        await update.message.reply_text("شناسه سفارش نامعتبر است.")
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, user_id, plan_id, server_id, amount, payment_method, status, admin_note, created_at
        FROM orders
        WHERE id = ?
        """,
        (order_id,),
    )
    order = cur.fetchone()
    conn.close()

    if not order:
        await update.message.reply_text("سفارش پیدا نشد.")
        return

    _, uid, plan_id, server_id, amount, method, status, admin_note, created_at = order
    server = get_server(server_id) if server_id else None
    plan = get_plan(plan_id) if plan_id else None

    if not server or not plan:
        await update.message.reply_text("سفارش به سرور/پلن معتبر متصل نیست.")
        return

    expire_date = calc_expire_date(plan[3])
    try:
        assign_server(uid, server_id, expire_date)
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE orders
            SET status = 'approved',
                admin_note = ?
            WHERE id = ?
            """,
            ("approved by admin", order_id),
        )
        conn.commit()
        conn.close()

        await context.bot.send_message(
            chat_id=uid,
            text=(
                "✅ سفارش شما تایید شد.\n\n"
                f"{server_caption(server, plan)}\n\n"
                f"⏰ انقضا: {expire_date}"
            ),
        )
        await update.message.reply_text("✅ سفارش تایید شد و سرور برای کاربر ارسال شد.")
    except Exception as e:
        log_error(e)
        await update.message.reply_text("❌ تایید سفارش با خطا مواجه شد.")


async def rejectorder_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    if not context.args:
        await update.message.reply_text("نمونه:\n/rejectorder 12")
        return

    order_id = parse_int(context.args[0])
    if not order_id:
        await update.message.reply_text("شناسه سفارش نامعتبر است.")
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT user_id
        FROM orders
        WHERE id = ?
        """,
        (order_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        await update.message.reply_text("سفارش پیدا نشد.")
        return

    uid = row[0]
    cur.execute(
        """
        UPDATE orders
        SET status = 'rejected',
            admin_note = ?
        WHERE id = ?
        """,
        ("rejected by admin", order_id),
    )
    conn.commit()
    conn.close()

    try:
        await context.bot.send_message(
            chat_id=uid,
            text="❌ سفارش شما رد شد. لطفاً با پشتیبانی در ارتباط باشید."
        )
    except Exception:
        pass

    await update.message.reply_text("✅ سفارش رد شد.")


async def pendingtickets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    rows = get_open_tickets()
    if not rows:
        await update.message.reply_text("تیکت بازی وجود ندارد.")
        return

    lines = ["🎫 تیکت‌های باز:\n"]
    for row in rows[:20]:
        # current schema after compat has username column
        ticket_id = row[0]
        uid = row[1]
        username = row[2] if len(row) > 2 else ""
        message = row[3] if len(row) > 3 else ""
        created_at = row[5] if len(row) > 5 else row[4]
        short = message if len(str(message)) <= 40 else str(message)[:37] + "..."
        lines.append(f"#{ticket_id} | {uid} {username} | {short}")

    await update.message.reply_text("\n".join(lines))


async def viewticket_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    if not context.args:
        await update.message.reply_text("نمونه:\n/viewticket 12")
        return

    ticket_id = parse_int(context.args[0])
    if not ticket_id:
        await update.message.reply_text("شناسه نامعتبر است.")
        return

    ticket = get_ticket(ticket_id)
    if not ticket:
        await update.message.reply_text("تیکت پیدا نشد.")
        return

    ticket_id, uid, username, message, status, created_at = ticket[:6]
    replies = get_replies(ticket_id)

    text = (
        f"🎫 تیکت #{ticket_id}\n"
        f"کاربر: {uid} {username}\n"
        f"وضعیت: {status}\n"
        f"زمان: {created_at}\n\n"
        f"متن:\n{message}\n"
    )

    if replies:
        text += "\nپاسخ‌ها:\n"
        for r in replies:
            rid, tid, admin_id, msg, r_created_at = r
            text += f"- {admin_id}: {msg}\n"

    await update.message.reply_text(text)


async def replyticket_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text("نمونه:\n/replyticket 12 سلام شما")
        return

    ticket_id = parse_int(context.args[0])
    message = " ".join(context.args[1:]).strip()
    if not ticket_id or not message:
        await update.message.reply_text("پارامترها ناقص است.")
        return

    ticket = get_ticket(ticket_id)
    if not ticket:
        await update.message.reply_text("تیکت پیدا نشد.")
        return

    uid = ticket[1]
    try:
        save_reply(ticket_id, user.id, message)
        close_ticket(ticket_id)
        await context.bot.send_message(
            chat_id=uid,
            text=f"📨 پاسخ پشتیبانی:\n\n{message}"
        )
        await update.message.reply_text("✅ پاسخ ارسال و تیکت بسته شد.")
    except Exception as e:
        log_error(e)
        await update.message.reply_text("❌ ارسال پاسخ با خطا مواجه شد.")


async def closeticket_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    if not context.args:
        await update.message.reply_text("نمونه:\n/closeticket 12")
        return

    ticket_id = parse_int(context.args[0])
    if not ticket_id:
        await update.message.reply_text("شناسه نامعتبر است.")
        return

    close_ticket(ticket_id)
    await update.message.reply_text("✅ تیکت بسته شد.")


async def pendingcomplaints_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    rows = get_open_complaints()
    if not rows:
        await update.message.reply_text("انتقاد/شکایتی باز نیست.")
        return

    lines = ["💭 انتقادها / شکایت‌های باز:\n"]
    for row in rows[:20]:
        cid = row[0]
        uid = row[1]
        username = row[2] if len(row) > 2 else ""
        message = row[3] if len(row) > 3 else ""
        lines.append(f"#{cid} | {uid} {username} | {message[:40]}")

    await update.message.reply_text("\n".join(lines))


async def replycomplaint_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text("نمونه:\n/replycomplaint 12 بررسی شد")
        return

    complaint_id = parse_int(context.args[0])
    message = " ".join(context.args[1:]).strip()
    if not complaint_id or not message:
        await update.message.reply_text("پارامترها ناقص است.")
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT user_id
        FROM complaints
        WHERE id = ?
        """,
        (complaint_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        await update.message.reply_text("مورد پیدا نشد.")
        return

    uid = row[0]
    cur.execute(
        """
        UPDATE complaints
        SET admin_reply = ?,
            status = 'closed'
        WHERE id = ?
        """,
        (message, complaint_id),
    )
    conn.commit()
    conn.close()

    try:
        await context.bot.send_message(
            chat_id=uid,
            text=f"📩 پاسخ شما:\n\n{message}"
        )
    except Exception:
        pass

    await update.message.reply_text("✅ پاسخ انتقاد/شکایت ثبت شد.")


async def closecomplaint_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    if not context.args:
        await update.message.reply_text("نمونه:\n/closecomplaint 12")
        return

    complaint_id = parse_int(context.args[0])
    if not complaint_id:
        await update.message.reply_text("شناسه نامعتبر است.")
        return

    close_complaint(complaint_id)
    await update.message.reply_text("✅ انتقاد/شکایت بسته شد.")


async def pendingpayments_view_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    rows = get_pending_payments()
    if not rows:
        await update.message.reply_text("پرداخت معلقی وجود ندارد.")
        return

    lines = ["💳 پرداخت‌های معلق:\n"]
    keyboard = []
    for row in rows[:20]:
        pay_id, uid, amount, receipt_file_id, status, reviewed_at, created_at = row
        lines.append(f"#{pay_id} | کاربر {uid} | {amount:,} تومان")
        keyboard.append([InlineKeyboardButton(f"پرداخت #{pay_id}", callback_data=f"pay_open:{pay_id}")])

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def approvepayment_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    if not context.args:
        await update.message.reply_text("نمونه:\n/approvepayment 12")
        return

    pay_id = parse_int(context.args[0])
    if not pay_id:
        await update.message.reply_text("شناسه نامعتبر است.")
        return

    payment = get_payment(pay_id)
    if not payment:
        await update.message.reply_text("پرداخت پیدا نشد.")
        return

    ok = approve_payment(pay_id)
    if ok:
        uid = payment[1]
        amount = payment[2]
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "✅ رسید شما تایید شد.\n"
                    f"موجودی شما به اندازه {amount:,} تومان افزایش یافت."
                ),
            )
        except Exception:
            pass
        await update.message.reply_text("✅ پرداخت تایید شد.")
    else:
        await update.message.reply_text("❌ تایید پرداخت ناموفق بود.")


async def rejectpayment_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    if not context.args:
        await update.message.reply_text("نمونه:\n/rejectpayment 12")
        return

    pay_id = parse_int(context.args[0])
    if not pay_id:
        await update.message.reply_text("شناسه نامعتبر است.")
        return

    payment = get_payment(pay_id)
    if not payment:
        await update.message.reply_text("پرداخت پیدا نشد.")
        return

    ok = reject_payment(pay_id)
    if ok:
        uid = payment[1]
        try:
            await context.bot.send_message(
                chat_id=uid,
                text="❌ رسید شما تایید نشد. لطفاً دوباره تلاش کنید."
            )
        except Exception:
            pass
        await update.message.reply_text("✅ پرداخت رد شد.")
    else:
        await update.message.reply_text("❌ رد پرداخت ناموفق بود.")


async def addsong_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    set_flow(context, "add_song_file")
    await update.message.reply_text(
        "فایل آهنگ را ارسال کنید.\n"
        "فرمت: audio یا document"
    )


async def delsong_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    if not context.args:
        await update.message.reply_text("نمونه:\n/delsong 12")
        return

    song_id = parse_int(context.args[0])
    if not song_id:
        await update.message.reply_text("شناسه نامعتبر است.")
        return

    try:
        delete_song(song_id)
        await update.message.reply_text("✅ آهنگ حذف شد.")
    except Exception as e:
        log_error(e)
        await update.message.reply_text("❌ حذف آهنگ ناموفق بود.")


async def addplan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    set_flow(context, "add_plan_title")
    await update.message.reply_text("عنوان پلن را ارسال کنید.")


async def addserver_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    set_flow(context, "add_server_plan")
    await update.message.reply_text("شناسه پلن را ارسال کنید.")


async def addtest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    set_flow(context, "add_test_server")
    await update.message.reply_text("کانفیگ سرور تست را ارسال کنید.")


async def myservers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    rows = get_user_servers(user.id)
    if not rows:
        await update.message.reply_text("هنوز سرویسی برای شما ثبت نشده است.")
        return

    lines = ["🌐 سرویس‌های شما:\n"]
    for row in rows:
        # id, user_id, server_id, assigned_at, expire_date, status
        rid = row[0]
        uid = row[1]
        server_id = row[2]
        assigned_at = row[3]
        expire_date = row[4]
        status = row[5] if len(row) > 5 else "active"
        server = get_server(server_id)
        server_name = server[2] if server else str(server_id)
        lines.append(f"#{rid} | {server_name} | {status} | انقضا: {expire_date}")

    await update.message.reply_text("\n".join(lines))


async def setfeature_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await feature_cmd(update, context)


async def resettest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_owner_panel_access(user.id):
        return

    if not context.args:
        await update.message.reply_text("نمونه:\n/resettest 123456")
        return

    target = parse_int(context.args[0])
    if not target:
        await update.message.reply_text("آیدی نامعتبر است.")
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM vpn_test_users WHERE user_id = ?", (target,))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ تست برای کاربر بازنشانی شد.")


async def resettestall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_owner_panel_access(user.id):
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM vpn_test_users")
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ تست برای همه کاربران بازنشانی شد.")


async def complaint_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_feature_enabled("support_enabled", True):
        await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
        return

    text = " ".join(context.args).strip()
    if text:
        create_complaint(user.id, user.username or str(user.id), text)
        notify_admins(
            context,
            f"💭 انتقاد/شکایت جدید\n\nکاربر: {user.id}\nیوزرنیم: {safe_username(user)}\nمتن:\n{text}",
        )
        await update.message.reply_text("✅ انتقاد/شکایت ثبت شد.")
        return

    set_flow(context, "complaint_wait")
    await update.message.reply_text("متن انتقاد/شکایت را ارسال کنید.")


async def ticket_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_feature_enabled("support_enabled", True):
        await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
        return

    text = " ".join(context.args).strip()
    if text:
        create_ticket(user.id, user.username or str(user.id), text)
        notify_admins(
            context,
            f"🎫 تیکت جدید\n\nکاربر: {user.id}\nیوزرنیم: {safe_username(user)}\nمتن:\n{text}",
        )
        await update.message.reply_text("✅ تیکت ثبت شد.")
        return

    set_flow(context, "ticket_wait")
    await update.message.reply_text("متن تیکت را ارسال کنید.")


async def setcard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await setcard_cmd(update, context)


# =============================
# Text / media flow handlers
# =============================

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    flow = get_flow(context)
    state = flow.get(FLOW_STATE)

    if not state:
        return

    message = update.message

    try:
        if state == "add_song_file":
            if message.audio:
                file_id = store_media("audio", message.audio.file_id)
            elif message.document:
                file_id = store_media("document", message.document.file_id)
            else:
                await message.reply_text("فقط فایل audio یا document ارسال کنید.")
                return

            flow["file_id"] = file_id
            flow[FLOW_STATE] = "add_song_title"
            set_flow(context, **flow)
            await message.reply_text("نام آهنگ را ارسال کنید.")
            return

        if state == "wallet_topup_receipt":
            if message.photo:
                file_id = store_media("photo", message.photo[-1].file_id)
            elif message.document:
                file_id = store_media("document", message.document.file_id)
            else:
                await message.reply_text("فقط عکس یا فایل رسید ارسال کنید.")
                return

            amount = flow.get("amount")
            create_payment(user.id, amount, file_id)
            notify_admins(
                context,
                f"💳 پرداخت جدید\n\nکاربر: {user.id}\nنام: {user_label(user)}\nمبلغ: {amount:,} تومان",
            )
            clear_flow(context)
            await message.reply_text("✅ رسید ثبت شد و در انتظار تایید ادمین است.")
            return

    except Exception as e:
        log_error(e)
        await message.reply_text("❌ خطایی رخ داد.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()

    add_user(user.id, user.username, user.full_name)
    update_last_seen(user.id)
    ensure_wallet_row(user.id)

    if is_banned(user.id):
        await update.message.reply_text("⛔ حساب شما مسدود است.")
        return

    if is_spam(user.id):
        await update.message.reply_text("⛔ لطفاً کمی صبر کنید.")
        return

    flow = get_flow(context)
    state = flow.get(FLOW_STATE)

    # -------------------------
    # Active flows
    # -------------------------
    try:
        if state == "broadcast_wait":
            sent = 0
            for row in get_all_users():
                uid = int(row[1])
                try:
                    await context.bot.send_message(chat_id=uid, text=text)
                    sent += 1
                except Exception:
                    pass
            clear_flow(context)
            await update.message.reply_text(f"✅ پیام برای {sent} کاربر ارسال شد.")
            return

        if state == "set_welcome_wait":
            set_setting("welcome_text", text)
            clear_flow(context)
            await update.message.reply_text("✅ متن خوش‌آمد ذخیره شد.")
            return

        if state == "add_song_title":
            flow["title"] = text
            flow[FLOW_STATE] = "add_song_category"
            set_flow(context, **flow)
            await update.message.reply_text("دسته‌بندی را ارسال کنید یا از سبک‌های پیشنهادی استفاده کنید:")
            return

        if state == "add_song_category":
            title = flow.get("title")
            file_id = flow.get("file_id")
            category = text
            add_song(title, file_id, category)
            clear_flow(context)
            await update.message.reply_text(f"✅ آهنگ «{title}» ذخیره شد.")
            return

        if state == "wallet_topup_amount":
            amount = parse_int(text)
            if not amount or amount <= 0:
                await update.message.reply_text("مبلغ معتبر نیست. فقط عدد ارسال کنید.")
                return

            flow["amount"] = amount
            flow[FLOW_STATE] = "wallet_topup_receipt"
            set_flow(context, **flow)

            card_number, card_holder = get_payment_card_info()
            await update.message.reply_text(
                f"✅ مبلغ {amount:,} تومان ثبت شد.\n\n"
                f"شماره کارت: {card_number or 'ثبت نشده'}\n"
                f"نام صاحب کارت: {card_holder or 'ثبت نشده'}\n\n"
                "اکنون عکس یا فایل رسید را ارسال کنید."
            )
            return

        if state == "search_song":
            keyword = text
            results = search_song(keyword)
            flow["results"] = results
            flow["query"] = keyword
            flow["mode"] = "search"
            flow[FLOW_STATE] = "song_view"
            set_flow(context, **flow)

            if not results:
                clear_flow(context)
                await update.message.reply_text("❌ آهنگی پیدا نشد.")
                return

            await show_song_list(update.message, context, results, f"🔍 نتایج جستجو برای «{keyword}»", "search", 0)
            return

        if state == "ticket_wait":
            create_ticket(user.id, user.username or str(user.id), text)
            notify_admins(
                context,
                f"🎫 تیکت جدید\n\nکاربر: {user.id}\nیوزرنیم: {safe_username(user)}\nمتن:\n{text}",
            )
            clear_flow(context)
            await update.message.reply_text("✅ تیکت ثبت شد.")
            return

        if state == "complaint_wait":
            create_complaint(user.id, user.username or str(user.id), text)
            notify_admins(
                context,
                f"💭 انتقاد/شکایت جدید\n\nکاربر: {user.id}\nیوزرنیم: {safe_username(user)}\nمتن:\n{text}",
            )
            clear_flow(context)
            await update.message.reply_text("✅ انتقاد/شکایت ثبت شد.")
            return

        if state == "corporate_wait":
            create_ticket(
                user.id,
                user.username or str(user.id),
                f"سرویس سازمانی:\n{text}",
            )
            notify_admins(
                context,
                f"🏢 درخواست سازمانی\n\nکاربر: {user.id}\nیوزرنیم: {safe_username(user)}\nمتن:\n{text}",
            )
            clear_flow(context)
            await update.message.reply_text("✅ درخواست سازمانی ثبت شد.")
            return

        if state == "add_plan_title":
            flow["title"] = text
            flow[FLOW_STATE] = "add_plan_volume"
            set_flow(context, **flow)
            await update.message.reply_text("حجم پلن را ارسال کنید. مثال: 10GB")
            return

        if state == "add_plan_volume":
            flow["volume"] = text
            flow[FLOW_STATE] = "add_plan_duration"
            set_flow(context, **flow)
            await update.message.reply_text("مدت پلن را ارسال کنید. مثال: 30 روز")
            return

        if state == "add_plan_duration":
            flow["duration"] = text
            flow[FLOW_STATE] = "add_plan_price"
            set_flow(context, **flow)
            await update.message.reply_text("قیمت پلن را فقط به صورت عددی ارسال کنید.")
            return

        if state == "add_plan_price":
            price = parse_int(text)
            if not price or price <= 0:
                await update.message.reply_text("قیمت نامعتبر است.")
                return
            add_plan(flow["title"], flow["volume"], flow["duration"], price)
            clear_flow(context)
            await update.message.reply_text("✅ پلن VPN اضافه شد.")
            return

        if state == "add_server_plan":
            plan_id = parse_int(text)
            if not plan_id:
                await update.message.reply_text("شناسه پلن نامعتبر است.")
                return
            flow["plan_id"] = plan_id
            flow[FLOW_STATE] = "add_server_name"
            set_flow(context, **flow)
            await update.message.reply_text("نام سرور را ارسال کنید.")
            return

        if state == "add_server_name":
            flow["server_name"] = text
            flow[FLOW_STATE] = "add_server_location"
            set_flow(context, **flow)
            await update.message.reply_text("لوکیشن سرور را ارسال کنید.")
            return

        if state == "add_server_location":
            flow["location"] = text
            flow[FLOW_STATE] = "add_server_config"
            set_flow(context, **flow)
            await update.message.reply_text("کانفیگ/اطلاعات سرور را ارسال کنید.")
            return

        if state == "add_server_config":
            add_server(
                flow["plan_id"],
                flow["server_name"],
                flow["location"],
                text,
            )
            clear_flow(context)
            await update.message.reply_text("✅ سرور اضافه شد.")
            return

        if state == "add_test_server":
            add_test_server(text)
            clear_flow(context)
            await update.message.reply_text("✅ سرور تست ذخیره شد.")
            return

        if state == "set_card_wait":
            if "|" not in text:
                await update.message.reply_text("فرمت درست نیست. مثال:\n6037-.... | نام صاحب کارت")
                return
            number, holder = [x.strip() for x in text.split("|", 1)]
            set_setting(DEFAULT_CARD_NUMBER, number)
            set_setting(DEFAULT_CARD_HOLDER, holder)
            clear_flow(context)
            await update.message.reply_text("✅ اطلاعات کارت ذخیره شد.")
            return

    except Exception as e:
        log_error(e)
        clear_flow(context)
        await update.message.reply_text("❌ خطایی رخ داد.")
        return

    # -------------------------
    # Main menu
    # -------------------------
    if text == "🔱 بخش موزیک":
        if not is_feature_enabled("music_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        clear_flow(context)
        await update.message.reply_text("🎵 بخش موزیک:", reply_markup=music_menu())
        return

    if text == "💣 بخش VPN":
        if not is_feature_enabled("vpn_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        clear_flow(context)
        await update.message.reply_text("🌐 بخش VPN:", reply_markup=vpn_menu())
        return

    if text == "🔙 بازگشت":
        clear_flow(context)
        await update.message.reply_text("منوی اصلی:", reply_markup=main_menu())
        return

    # -------------------------
    # Music section
    # -------------------------
    if text == "🎶 لیست آهنگ ها":
        if not is_feature_enabled("music_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        songs = get_all_songs()
        if not songs:
            await update.message.reply_text("فعلاً آهنگی ثبت نشده است.")
            return
        set_flow(context, song_view=True, state="song_view", mode="all", page=0)
        await show_song_list(update.message, context, songs, "🎶 لیست آهنگ‌ها", "all", 0)
        return

    if text == "🔥 جدید و محبوب":
        if not is_feature_enabled("music_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🆕 جدیدترین‌ها", callback_data="songkind:new")],
                [InlineKeyboardButton("⭐ محبوب‌ترین‌ها", callback_data="songkind:top")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="songback:main")],
            ]
        )
        await update.message.reply_text("یکی از گزینه‌ها را انتخاب کنید:", reply_markup=keyboard)
        return

    if text == "📈 آهنگ های ترند":
        if not is_feature_enabled("music_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        songs = get_top_songs(50)
        if not songs:
            await update.message.reply_text("فعلاً آهنگی ثبت نشده است.")
            return
        set_flow(context, state="song_view", mode="top", page=0)
        await show_song_list(update.message, context, songs, "📈 آهنگ‌های ترند", "top", 0)
        return

    if text == "🔍 جستجوی آهنگ":
        if not is_feature_enabled("music_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        set_flow(context, state="search_song")
        await update.message.reply_text("نام یا بخشی از نام آهنگ را ارسال کنید.")
        return

    if text == "🎲 پیشنهاد رندوم":
        if not is_feature_enabled("music_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🎲 آهنگ رندوم", callback_data="random:any")],
                [InlineKeyboardButton("🎼 بر اساس سبک", callback_data="random:style")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="songback:main")],
            ]
        )
        await update.message.reply_text("پیشنهاد رندوم:", reply_markup=keyboard)
        return

    # -------------------------
    # VPN section
    # -------------------------
    if text == "💳 تعرفه سرورها":
        if not is_feature_enabled("vpn_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        plans = get_plans()
        if not plans:
            await update.message.reply_text("فعلاً تعرفه‌ای ثبت نشده است.")
            return
        set_flow(context, state="plan_view", page=0)
        await show_plan_list(update.message, context, plans, "💳 تعرفه سرورها", 0)
        return

    if text == "🧪 سرور تست":
        if not is_feature_enabled("vpn_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        await send_test_server_to_user(update, context)
        return

    if text == "👛 کیف پول":
        if not is_feature_enabled("wallet_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        bal = get_balance(user.id)
        card_number, card_holder = get_payment_card_info()
        await update.message.reply_text(
            f"👛 کیف پول شما\n\n"
            f"نام: {user.full_name}\n"
            f"یوزرنیم: {safe_username(user) or 'ندارد'}\n"
            f"موجودی: {bal:,} تومان\n\n"
            f"شماره کارت: {card_number or 'ثبت نشده'}\n"
            f"صاحب کارت: {card_holder or 'ثبت نشده'}",
            reply_markup=wallet_menu(),
        )
        return

    if text == "➕ افزایش موجودی":
        if not is_feature_enabled("wallet_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        set_flow(context, state="wallet_topup_amount")
        await update.message.reply_text("مبلغ شارژ را فقط به صورت عددی ارسال کنید.")
        return

    if text == "📜 تراکنش ها":
        if not is_feature_enabled("wallet_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        rows = get_wallet_transactions(user.id, limit=10)
        if not rows:
            await update.message.reply_text("تراکنشی ثبت نشده است.")
            return
        lines = ["📜 تراکنش‌های کیف پول:\n"]
        for r in rows:
            rid, amount, tx_type, status, note, created_at = r
            lines.append(f"#{rid} | {tx_type} | {amount:,} | {status} | {created_at}")
        await update.message.reply_text("\n".join(lines))
        return

    if text == "📞 پشتیبانی":
        if not is_feature_enabled("support_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        set_flow(context, state="ticket_wait")
        await update.message.reply_text("پیام پشتیبانی خود را ارسال کنید.")
        return

    if text == "🏢 سرویس سازمانی":
        if not is_feature_enabled("vpn_enabled", True) and not has_admin_access(user.id):
            await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
            return
        set_flow(context, state="corporate_wait")
        await update.message.reply_text("متن درخواست سازمانی را ارسال کنید.")
        return

    # -------------------------
    # Hidden complaint route
    # -------------------------
    if text in {"💭 انتقاد", "📝 انتقاد / پیشنهاد", "/complaint"}:
        set_flow(context, state="complaint_wait")
        await update.message.reply_text("متن انتقاد/پیشنهاد را ارسال کنید.")
        return

    # -------------------------
    # Admin / owner menus
    # -------------------------
    if text == "👮 مدیریت ادمین ها":
        if not has_owner_panel_access(user.id):
            return
        await update.message.reply_text(
            "مدیریت ادمین‌ها:\n\n"
            "/addadmin <id> <vpn/music/support/temp>\n"
            "/removeadmin <id>\n"
            "/admins"
        )
        return

    if text == "📢 پیام همگانی":
        if not has_owner_panel_access(user.id):
            return
        set_flow(context, state="broadcast_wait")
        await update.message.reply_text("متن پیام همگانی را ارسال کنید.")
        return

    if text == "⚙ تنظیمات":
        if not has_owner_panel_access(user.id):
            return
        card_number, card_holder = get_payment_card_info()
        await update.message.reply_text(
            "⚙ تنظیمات فعلی\n\n"
            f"شماره کارت: {card_number or 'ثبت نشده'}\n"
            f"صاحب کارت: {card_holder or 'ثبت نشده'}\n\n"
            f"{get_feature_text()}\n\n"
            "تغییرات:\n"
            "/setcard <number> | <holder>\n"
            "/setwelcome <text>\n"
            "/feature <name> on/off"
        )
        return

    if text == "📊 آمار کامل" or text == "📊 آمار کاربران":
        await stats_cmd(update, context)
        return

    if text == "💰 بررسی پرداخت ها":
        await pendingpayments_view_cmd(update, context)
        return

    if text == "🎫 تیکت ها":
        await pendingtickets_cmd(update, context)
        return

    if text == "🌐 سرورها":
        plans = get_plans()
        if not plans:
            await update.message.reply_text("تعرفه‌ای ثبت نشده است.")
            return
        await update.message.reply_text("برای دیدن پلن‌ها از /vpn یا تعرفه‌ها استفاده کنید.")
        return

    if text == "🎵 مدیریت موزیک":
        await update.message.reply_text(
            "مدیریت موزیک:\n"
            "/addsong\n"
            "/delsong <id>\n"
            "/songstats"
        )
        return

    # Default fallback
    await update.message.reply_text("از منوی ربات استفاده کنید.")


# =============================
# Callback handler
# =============================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if is_banned(user.id):
        await query.edit_message_text("⛔ حساب شما مسدود است.")
        return

    data = query.data or ""

    try:
        # -------------------
        # Music list paging
        # -------------------
        if data.startswith("songpage:"):
            direction = data.split(":", 1)[1]
            flow = get_flow(context)
            mode = flow.get("mode", "all")
            page = int(flow.get("page", 0))
            if direction == "next":
                page += 1
            elif direction == "prev":
                page = max(0, page - 1)

            songs = resolve_song_list(flow)
            title_map = {
                "all": "🎶 لیست آهنگ‌ها",
                "new": "🆕 جدیدترین آهنگ‌ها",
                "top": "⭐ محبوب‌ترین آهنگ‌ها",
                "search": f"🔍 نتایج جستجو برای «{flow.get('query','')}»",
                "category": f"📂 آهنگ‌های سبک «{flow.get('category','')}»",
            }
            title = title_map.get(mode, "🎶 لیست آهنگ‌ها")
            await edit_song_list(query, context, songs, title, mode, page)
            return

        if data.startswith("songkind:"):
            kind = data.split(":", 1)[1]
            if kind == "new":
                songs = get_new_songs(50)
                set_flow(context, state="song_view", mode="new", page=0)
                await edit_song_list(query, context, songs, "🆕 جدیدترین آهنگ‌ها", "new", 0)
                return
            if kind == "top":
                songs = get_top_songs(50)
                set_flow(context, state="song_view", mode="top", page=0)
                await edit_song_list(query, context, songs, "⭐ محبوب‌ترین آهنگ‌ها", "top", 0)
                return

        if data.startswith("song_open:"):
            song_id = parse_int(data.split(":", 1)[1])
            song = get_song(song_id)
            if not song:
                await query.edit_message_text("آهنگ پیدا نشد.")
                return
            await context.bot.send_message(
                chat_id=user.id,
                text=song_caption(song),
                reply_markup=build_rating_keyboard(song_id),
            )
            kind, raw_id = file_kind_and_id(song[2])
            try:
                if kind == "document":
                    await context.bot.send_document(
                        chat_id=user.id,
                        document=raw_id,
                        caption=song_caption(song),
                        reply_markup=build_rating_keyboard(song_id),
                    )
                else:
                    await context.bot.send_audio(
                        chat_id=user.id,
                        audio=raw_id,
                        caption=song_caption(song),
                        reply_markup=build_rating_keyboard(song_id),
                    )
                increase_download(song_id)
            except Exception as e:
                log_error(e)
                await context.bot.send_message(chat_id=user.id, text="❌ ارسال آهنگ با خطا مواجه شد.")
            return

        if data.startswith("rate:"):
            _, song_id, score = data.split(":", 2)
            song_id = parse_int(song_id)
            score = parse_int(score, 1) or 1
            add_song_score(song_id, score)
            await query.answer(f"⭐ امتیاز {score} ثبت شد.")
            return

        if data == "songback:main":
            await query.edit_message_text("منوی اصلی", reply_markup=main_menu())
            return

        if data == "random:any":
            song = get_random_song()
            if not song:
                await query.edit_message_text("فعلاً آهنگی ثبت نشده است.")
                return
            await context.bot.send_message(
                chat_id=user.id,
                text=song_caption(song),
                reply_markup=build_rating_keyboard(song[0]),
            )
            kind, raw_id = file_kind_and_id(song[2])
            if kind == "document":
                await context.bot.send_document(
                    chat_id=user.id,
                    document=raw_id,
                    caption=song_caption(song),
                    reply_markup=build_rating_keyboard(song[0]),
                )
            else:
                await context.bot.send_audio(
                    chat_id=user.id,
                    audio=raw_id,
                    caption=song_caption(song),
                    reply_markup=build_rating_keyboard(song[0]),
                )
            increase_download(song[0])
            return

        if data == "random:style":
            await query.edit_message_text(
                "سبک موردنظر را انتخاب کنید:",
                reply_markup=build_category_keyboard(prefix="randcat"),
            )
            return

        if data.startswith("randcat:"):
            cat = data.split(":", 1)[1]
            song = get_random_song_by_category(cat)
            if not song:
                await query.edit_message_text("در این سبک آهنگی ثبت نشده است.")
                return
            await context.bot.send_message(
                chat_id=user.id,
                text=song_caption(song),
                reply_markup=build_rating_keyboard(song[0]),
            )
            kind, raw_id = file_kind_and_id(song[2])
            if kind == "document":
                await context.bot.send_document(
                    chat_id=user.id,
                    document=raw_id,
                    caption=song_caption(song),
                    reply_markup=build_rating_keyboard(song[0]),
                )
            else:
                await context.bot.send_audio(
                    chat_id=user.id,
                    audio=raw_id,
                    caption=song_caption(song),
                    reply_markup=build_rating_keyboard(song[0]),
                )
            increase_download(song[0])
            return

        # -------------------
        # Plan list / server view
        # -------------------
        if data.startswith("planpage:"):
            direction = data.split(":", 1)[1]
            page = int(context.user_data.get("plan_view", {}).get("page", 0))
            if direction == "next":
                page += 1
            else:
                page = max(0, page - 1)
            plans = get_plans()
            await edit_plan_list(query, context, plans, "💳 تعرفه سرورها", page)
            return

        if data.startswith("plan_open:"):
            plan_id = parse_int(data.split(":", 1)[1])
            plan = get_plan(plan_id)
            if not plan:
                await query.edit_message_text("پلن پیدا نشد.")
                return

            servers = get_servers(plan_id)
            keyboard = []
            for server in servers[:20]:
                server_id, p_id, server_name, location, config_text, is_used, created_at = server
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"{server_name} | {location}",
                            callback_data=f"server_open:{server_id}",
                        )
                    ]
                )
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="planback:list")])

            text = (
                plan_caption(plan)
                + "\n\nسرورهای موجود را انتخاب کنید."
            )
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if data.startswith("server_open:"):
            server_id = parse_int(data.split(":", 1)[1])
            server = get_server(server_id)
            if not server:
                await query.edit_message_text("سرور پیدا نشد.")
                return
            plan = get_plan(server[1])
            if not plan:
                await query.edit_message_text("پلن مرتبط پیدا نشد.")
                return

            text = server_caption(server, plan)
            await query.edit_message_text(text, reply_markup=build_server_keyboard(server_id, plan[0]))
            return

        if data.startswith("server_pay_wallet:"):
            server_id = parse_int(data.split(":", 1)[1])
            server = get_server(server_id)
            if not server:
                await query.edit_message_text("سرور پیدا نشد.")
                return
            if server[5]:
                await query.edit_message_text("این سرور قبلاً استفاده شده است.")
                return

            plan = get_plan(server[1])
            if not plan:
                await query.edit_message_text("پلن پیدا نشد.")
                return

            price = int(plan[4])
            balance = get_balance(user.id)
            if balance < price:
                await query.edit_message_text(
                    f"موجودی شما کافی نیست.\n\nموجودی: {balance:,}\nقیمت: {price:,}"
                )
                return

            ok, new_balance = subtract_balance(user.id, price, f"buy server #{server_id}")
            if not ok:
                await query.edit_message_text("موجودی کافی نیست.")
                return

            expire_date = calc_expire_date(plan[3])
            assign_server(user.id, server_id, expire_date)

            await context.bot.send_message(
                chat_id=user.id,
                text=(
                    "✅ خرید شما با کیف پول انجام شد.\n\n"
                    f"{server_caption(server, plan)}\n\n"
                    f"⏰ انقضا: {expire_date}\n"
                    f"💰 موجودی جدید: {new_balance:,} تومان\n\n"
                    f"کانفیگ:\n{server[4]}"
                ),
            )
            await query.edit_message_text("✅ خرید با کیف پول تایید و سرویس ارسال شد.")
            return

        if data.startswith("server_pay_direct:"):
            server_id = parse_int(data.split(":", 1)[1])
            server = get_server(server_id)
            if not server:
                await query.edit_message_text("سرور پیدا نشد.")
                return
            plan = get_plan(server[1])
            if not plan:
                await query.edit_message_text("پلن پیدا نشد.")
                return

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO orders
                (user_id, plan_id, server_id, amount, payment_method, status, admin_note, created_at)
                VALUES (?, ?, ?, ?, 'direct', 'pending', ?, ?)
                """,
                (
                    user.id,
                    plan[0],
                    server_id,
                    int(plan[4]),
                    f"direct order from {user.id}",
                    now(),
                ),
            )
            conn.commit()
            conn.close()

            notify_admins(
                context,
                f"🛒 سفارش مستقیم جدید\n\nکاربر: {user.id}\nیوزرنیم: {safe_username(user)}\nپلن: {plan[1]}\nسرور: {server[2]}\nقیمت: {int(plan[4]):,}",
            )

            await context.bot.send_message(
                chat_id=user.id,
                text=(
                    "✅ سفارش شما ثبت شد و در انتظار تایید ادمین است.\n"
                    "پس از تایید، سرویس برای شما ارسال می‌شود."
                ),
            )
            await query.edit_message_text("✅ سفارش مستقیم ثبت شد.")
            return

        if data == "planback:main" or data == "planback:list":
            plans = get_plans()
            await edit_plan_list(query, context, plans, "💳 تعرفه سرورها", context.user_data.get("plan_view", {}).get("page", 0))
            return

        # -------------------
        # Payments
        # -------------------
        if data.startswith("pay_open:"):
            pay_id = parse_int(data.split(":", 1)[1])
            payment = get_payment(pay_id)
            if not payment:
                await query.edit_message_text("پرداخت پیدا نشد.")
                return
            await send_receipt_to_admin(user.id, context, payment)
            await query.edit_message_text(f"پرداخت #{pay_id} برای بررسی ارسال شد.")
            return

        if data.startswith("pay_approve:"):
            pay_id = parse_int(data.split(":", 1)[1])
            payment = get_payment(pay_id)
            if not payment:
                await query.edit_message_text("پرداخت پیدا نشد.")
                return
            if approve_payment(pay_id):
                uid = payment[1]
                amount = payment[2]
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=(
                            "✅ رسید شما تایید شد.\n"
                            f"موجودی شما به اندازه {amount:,} تومان افزایش یافت."
                        ),
                    )
                except Exception:
                    pass
                await query.edit_message_text(f"✅ پرداخت #{pay_id} تایید شد.")
            else:
                await query.edit_message_text("❌ تایید پرداخت ناموفق بود.")
            return

        if data.startswith("pay_reject:"):
            pay_id = parse_int(data.split(":", 1)[1])
            payment = get_payment(pay_id)
            if not payment:
                await query.edit_message_text("پرداخت پیدا نشد.")
                return
            if reject_payment(pay_id):
                uid = payment[1]
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text="❌ رسید شما تایید نشد. لطفاً دوباره تلاش کنید.",
                    )
                except Exception:
                    pass
                await query.edit_message_text(f"✅ پرداخت #{pay_id} رد شد.")
            else:
                await query.edit_message_text("❌ رد پرداخت ناموفق بود.")
            return

        # -------------------
        # Back buttons
        # -------------------
        if data == "randback:music":
            await query.edit_message_text("🎵 بخش موزیک", reply_markup=music_menu())
            return

        if data == "songback:main":
            await query.edit_message_text("منوی اصلی", reply_markup=main_menu())
            return

    except Exception as e:
        log_error(e)
        try:
            await query.edit_message_text("❌ خطا رخ داد.")
        except Exception:
            pass


# =============================
# Error handler
# =============================

async def error_handler(update, context):
    try:
        log_error(context.error)
    except Exception:
        pass


# =============================
# Main
# =============================

def main():
    ensure_compat_schema()
    init_database()
    bootstrap_owner()

    token = TOKEN
    if not token:
        print("BOT_TOKEN تنظیم نشده است")
        return

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("owner", owner_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("addadmin", addadmin_cmd))
    app.add_handler(CommandHandler("removeadmin", removeadmin_cmd))
    app.add_handler(CommandHandler("admins", admins_cmd))
    app.add_handler(CommandHandler("setcard", setcard_cmd))
    app.add_handler(CommandHandler("feature", feature_cmd))
    app.add_handler(CommandHandler("setwelcome", setwelcome_cmd))
    app.add_handler(CommandHandler("pendingpayments", pendingpayments_view_cmd))
    app.add_handler(CommandHandler("approvepayment", approvepayment_cmd))
    app.add_handler(CommandHandler("rejectpayment", rejectpayment_cmd))
    app.add_handler(CommandHandler("pendingorders", orders_cmd))
    app.add_handler(CommandHandler("approveorder", approveorder_cmd))
    app.add_handler(CommandHandler("rejectorder", rejectorder_cmd))
    app.add_handler(CommandHandler("tickets", pendingtickets_cmd))
    app.add_handler(CommandHandler("viewticket", viewticket_cmd))
    app.add_handler(CommandHandler("replyticket", replyticket_cmd))
    app.add_handler(CommandHandler("closeticket", closeticket_cmd))
    app.add_handler(CommandHandler("complaints", pendingcomplaints_cmd))
    app.add_handler(CommandHandler("replycomplaint", replycomplaint_cmd))
    app.add_handler(CommandHandler("closecomplaint", closecomplaint_cmd))
    app.add_handler(CommandHandler("addsong", addsong_cmd))
    app.add_handler(CommandHandler("delsong", delsong_cmd))
    app.add_handler(CommandHandler("addplan", addplan_cmd))
    app.add_handler(CommandHandler("addserver", addserver_cmd))
    app.add_handler(CommandHandler("addtest", addtest_cmd))
    app.add_handler(CommandHandler("myservers", myservers_cmd))
    app.add_handler(CommandHandler("resettest", resettest_cmd))
    app.add_handler(CommandHandler("resettestall", resettestall_cmd))
    app.add_handler(CommandHandler("complaint", complaint_cmd))
    app.add_handler(CommandHandler("ticket", ticket_cmd))

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Media and text
    app.add_handler(MessageHandler(filters.PHOTO | filters.AUDIO | filters.Document.ALL, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.add_error_handler(error_handler)

    log_info("Bot4 started")
    print("Bot4 started")
    app.run_polling()


if __name__ == "__main__":
    main()
