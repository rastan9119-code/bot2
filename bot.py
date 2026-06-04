import os
import re
from datetime import datetime, timedelta

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

try:
    from admin_panel import admin_keyboard
except Exception:
    def admin_keyboard():
        keyboard = [
            ["📊 آمار کاربران"],
            ["💰 بررسی پرداخت ها"],
            ["🌐 سرورها"],
            ["🎫 تیکت ها"],
            ["🎵 مدیریت موزیک"],
            ["🔙 بازگشت"],
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

from menus import (
    main_menu,
    music_menu,
    vpn_menu,
    wallet_menu,
    owner_menu,
)

try:
    from settings import get_setting, set_setting
except Exception:
    def get_setting(name):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT value
            FROM settings
            WHERE name = ?
            """,
            (name,),
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None

    def set_setting(name, value):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO settings (name, value)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET
                value = excluded.value
            """,
            (name, str(value)),
        )
        conn.commit()
        conn.close()

try:
    from anti_spam import is_spam
except Exception:
    def is_spam(user_id):
        return False

try:
    from logger import log_info, log_error
except Exception:
    def log_info(message):
        print(message)

    def log_error(error):
        print(error)

TOKEN = (os.getenv("BOT_TOKEN") or CONFIG_BOT_TOKEN or "").strip()

PAGE_SIZE_SONGS = 8
PAGE_SIZE_PLANS = 5

DEFAULT_CARD_NUMBER = "bank_card_number"
DEFAULT_CARD_HOLDER = "bank_card_holder"

FLOW_STATE = "state"

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


# -----------------------------
# Helpers
# -----------------------------

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_int(text, default=None):
    try:
        return int(str(text).strip())
    except Exception:
        return default


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


def clamp_page(page, total, page_size):
    if total <= 0:
        return 0
    max_page = max(0, (total - 1) // page_size)
    return max(0, min(page, max_page))


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


def get_payment_card_info():
    number = (get_setting(DEFAULT_CARD_NUMBER) or "").strip()
    holder = (get_setting(DEFAULT_CARD_HOLDER) or "").strip()
    return number, holder


def set_flow(context, state, **data):
    context.user_data["flow"] = {"state": state, **data}


def get_flow(context):
    return context.user_data.get("flow", {})


def clear_flow(context):
    context.user_data.pop("flow", None)


def is_primary_owner(user_id):
    return int(user_id) == int(OWNER_ID) or is_owner(user_id)


def can_see_owner_panel(user_id):
    return is_primary_owner(user_id) or is_temp_owner(user_id)


def can_manage_music(user_id):
    return is_primary_owner(user_id) or is_music_admin(user_id)


def can_manage_vpn(user_id):
    return is_primary_owner(user_id) or is_vpn_admin(user_id)


def has_admin_access(user_id):
    return (
        is_primary_owner(user_id)
        or is_temp_owner(user_id)
        or is_vpn_admin(user_id)
        or is_music_admin(user_id)
        or is_support_admin(user_id)
    )


def admin_ids_unique():
    ids = {int(OWNER_ID)}
    for uid, _role in owner_get_admins():
        ids.add(int(uid))

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


async def send_menu(context, chat_id, text, markup):
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=markup,
    )


def song_caption(song):
    song_id, title, file_id, category, score, downloads, is_active, created_at = song
    return (
        f"🎵 {title}\n"
        f"📂 دسته‌بندی: {category}\n"
        f"⭐ امتیاز: {float(score):.1f}\n"
        f"⬇️ دانلود: {downloads}"
    )


def plan_caption(plan):
    plan_id, title, volume, duration, price, created_at = plan
    return (
        f"💳 {title}\n"
        f"📦 حجم: {volume}\n"
        f"⏳ مدت: {duration}\n"
        f"💰 قیمت: {price:,} تومان"
    )


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


def build_rating_keyboard(song_id):
    keyboard = [[
        InlineKeyboardButton("⭐1", callback_data=f"rate:{song_id}:1"),
        InlineKeyboardButton("⭐2", callback_data=f"rate:{song_id}:2"),
        InlineKeyboardButton("⭐3", callback_data=f"rate:{song_id}:3"),
        InlineKeyboardButton("⭐4", callback_data=f"rate:{song_id}:4"),
        InlineKeyboardButton("⭐5", callback_data=f"rate:{song_id}:5"),
    ]]
    return InlineKeyboardMarkup(keyboard)


def build_category_keyboard(prefix="randcat"):
    cats = get_categories() or MUSIC_GENRES[:]
    keyboard = []
    row = []
    for cat in cats:
        row.append(InlineKeyboardButton(cat, callback_data=f"{prefix}:{cat}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="randback:music")])
    return InlineKeyboardMarkup(keyboard)


def build_song_keyboard(songs, page):
    total = len(songs)
    page = clamp_page(page, total, PAGE_SIZE_SONGS)
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
    return InlineKeyboardMarkup(keyboard), page, total


def build_plan_keyboard(plans, page):
    total = len(plans)
    page = clamp_page(page, total, PAGE_SIZE_PLANS)
    start = page * PAGE_SIZE_PLANS
    end = start + PAGE_SIZE_PLANS
    page_plans = plans[start:end]

    keyboard = []
    for plan in page_plans:
        plan_id, title, volume, duration, price, created_at = plan
        keyboard.append([
            InlineKeyboardButton(
                f"{title} | {price:,} تومان",
                callback_data=f"plan_open:{plan_id}",
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ قبلی", callback_data="planpage:prev"))
    if end < total:
        nav.append(InlineKeyboardButton("بعدی ▶️", callback_data="planpage:next"))
    if nav:
        keyboard.append(nav)

    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="planback:list")])
    return InlineKeyboardMarkup(keyboard), page, total


async def show_song_list(message, context, songs, title, page=0, mode="all", query_text="", category=""):
    context.user_data["song_view"] = {
        "state": "song_view",
        "mode": mode,
        "results": songs if mode == "search" else None,
        "query": query_text,
        "category": category,
        "page": page,
    }
    markup, page, total = build_song_keyboard(songs, page)
    start = page * PAGE_SIZE_SONGS
    end = min(start + PAGE_SIZE_SONGS, total)
    text = f"{title}\n\nنمایش {start + 1 if total else 0} تا {end} از {total}"
    await message.reply_text(text, reply_markup=markup)


async def edit_song_list(query, context, songs, title, page=0, mode="all", query_text="", category=""):
    context.user_data["song_view"] = {
        "state": "song_view",
        "mode": mode,
        "results": songs if mode == "search" else None,
        "query": query_text,
        "category": category,
        "page": page,
    }
    markup, page, total = build_song_keyboard(songs, page)
    start = page * PAGE_SIZE_SONGS
    end = min(start + PAGE_SIZE_SONGS, total)
    text = f"{title}\n\nنمایش {start + 1 if total else 0} تا {end} از {total}"
    await query.edit_message_text(text, reply_markup=markup)


async def show_plan_list(message, context, plans, title, page=0):
    context.user_data["plan_view"] = {"state": "plan_view", "page": page}
    markup, page, total = build_plan_keyboard(plans, page)
    start = page * PAGE_SIZE_PLANS
    end = min(start + PAGE_SIZE_PLANS, total)
    text = f"{title}\n\nنمایش {start + 1 if total else 0} تا {end} از {total}"
    await message.reply_text(text, reply_markup=markup)


async def edit_plan_list(query, context, plans, title, page=0):
    context.user_data["plan_view"] = {"state": "plan_view", "page": page}
    markup, page, total = build_plan_keyboard(plans, page)
    start = page * PAGE_SIZE_PLANS
    end = min(start + PAGE_SIZE_PLANS, total)
    text = f"{title}\n\nنمایش {start + 1 if total else 0} تا {end} از {total}"
    await query.edit_message_text(text, reply_markup=markup)


async def send_song_media(context, chat_id, song):
    song_id, title, file_id, category, score, downloads, is_active, created_at = song
    kind, raw_id = file_kind_and_id(file_id)
    caption = song_caption(song)

    if kind == "document":
        await context.bot.send_document(
            chat_id=chat_id,
            document=raw_id,
            caption=caption,
            reply_markup=build_rating_keyboard(song_id),
        )
    else:
        await context.bot.send_audio(
            chat_id=chat_id,
            audio=raw_id,
            caption=caption,
            reply_markup=build_rating_keyboard(song_id),
        )
    increase_download(song_id)


async def send_test_server_to_user(update, context):
    user = update.effective_user
    test_server = get_test_server()

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


def ensure_compat_schema():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        receipt_file_id TEXT,
        status TEXT DEFAULT 'pending',
        reviewed_at TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS replies(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER,
        admin_id INTEGER,
        message TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plan_id INTEGER,
        server_id INTEGER,
        amount INTEGER,
        payment_method TEXT,
        status TEXT DEFAULT 'pending',
        admin_note TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vpn_plans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        volume TEXT,
        duration TEXT,
        price INTEGER,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vpn_servers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER,
        server_name TEXT,
        location TEXT,
        config_text TEXT,
        is_used INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_vpn(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        server_id INTEGER,
        assigned_at TEXT,
        expire_date TEXT,
        status TEXT DEFAULT 'active'
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vpn_test(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_text TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vpn_test_users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        received_at TEXT
    )
    """)

    # compatible columns
    cur.execute("PRAGMA table_info(tickets)")
    ticket_cols = {r[1] for r in cur.fetchall()}
    if "username" not in ticket_cols:
        cur.execute("ALTER TABLE tickets ADD COLUMN username TEXT")
    if "admin_reply" not in ticket_cols:
        cur.execute("ALTER TABLE tickets ADD COLUMN admin_reply TEXT")

    cur.execute("PRAGMA table_info(complaints)")
    complaint_cols = {r[1] for r in cur.fetchall()}
    if "username" not in complaint_cols:
        cur.execute("ALTER TABLE complaints ADD COLUMN username TEXT")
    if "admin_reply" not in complaint_cols:
        cur.execute("ALTER TABLE complaints ADD COLUMN admin_reply TEXT")

    conn.commit()
    conn.close()

    # defaults
    if get_setting("welcome_text") is None:
        set_setting("welcome_text", WELCOME_TEXT.strip())

    if get_setting(DEFAULT_CARD_NUMBER) is None:
        set_setting(DEFAULT_CARD_NUMBER, "")

    if get_setting(DEFAULT_CARD_HOLDER) is None:
        set_setting(DEFAULT_CARD_HOLDER, "")

    for key, value in DEFAULT_FEATURES.items():
        set_feature_enabled(key, bool(value), "default")


def bootstrap_owner():
    try:
        set_owner(OWNER_ID, True)
    except Exception:
        pass


def ticket_parts(row):
    if not row:
        return None
    # id, user_id, username, message, status, admin_reply, created_at
    ticket_id = row[0]
    user_id = row[1]
    username = row[2] if len(row) > 2 else ""
    message = row[3] if len(row) > 3 else ""
    status = row[4] if len(row) > 4 else "open"
    admin_reply = row[5] if len(row) > 5 else ""
    created_at = row[6] if len(row) > 6 else ""
    return ticket_id, user_id, username, message, status, admin_reply, created_at


def complaint_parts(row):
    if not row:
        return None
    # id, user_id, username, message, status, admin_reply, created_at
    complaint_id = row[0]
    user_id = row[1]
    username = row[2] if len(row) > 2 else ""
    message = row[3] if len(row) > 3 else ""
    status = row[4] if len(row) > 4 else "open"
    admin_reply = row[5] if len(row) > 5 else ""
    created_at = row[6] if len(row) > 6 else ""
    return complaint_id, user_id, username, message, status, admin_reply, created_at


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


# -----------------------------
# Commands
# -----------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_banned(user.id):
        await update.message.reply_text("⛔ حساب شما مسدود است.")
        return

    add_user(user.id, user.username, user.full_name)
    update_last_seen(user.id)
    ensure_wallet(user.id)
    clear_flow(context)

    log_info(f"start: {user.id}")
    await update.message.reply_text(
        get_setting("welcome_text") or WELCOME_TEXT,
        reply_markup=main_menu(),
    )


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_flow(context)
    await update.message.reply_text("منوی اصلی:", reply_markup=main_menu())


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not has_admin_access(user.id):
        return

    clear_flow(context)

    if can_see_owner_panel(user.id):
        await update.message.reply_text(
            "👑/👮 پنل مدیریت\n\n"
            "دستورات سریع:\n"
            "/stats\n"
            "/pendingpayments\n"
            "/pendingorders\n"
            "/tickets\n"
            "/complaints\n"
            "/admins",
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
    if not can_see_owner_panel(user.id):
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

        text = (
            "📊 آمار کلی\n\n"
            f"👥 کاربران کل: {s.get('users', 0)}\n"
            f"📅 کاربران امروز: {s.get('today_users', 0)}\n"
            f"🎵 آهنگ‌ها: {song_stats.get('songs', 0)}\n"
            f"⬇️ دانلودها: {song_stats.get('downloads', 0)}\n"
            f"⭐ میانگین امتیاز: {song_stats.get('avg_score', 0.0):.1f}\n"
            f"🎫 تیکت‌ها: {s.get('tickets', 0)}\n"
            f"💳 پرداخت‌ها: {s.get('payments', 0)}\n"
            f"🌐 پلن‌ها: {s.get('vpn_plans', 0)}\n"
            f"🖥 سرورها: {s.get('vpn_servers', 0)}\n"
            f"👛 مجموع کیف پول: {s.get('wallet_total', 0):,} تومان"
        )
        await update.message.reply_text(text)
    except Exception as e:
        log_error(e)
        await update.message.reply_text("❌ خطا در دریافت آمار.")


async def songstats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not can_manage_music(user.id):
        return

    s = get_song_stats()
    await update.message.reply_text(
        "🎵 آمار موسیقی\n\n"
        f"تعداد آهنگ‌ها: {s.get('songs', 0)}\n"
        f"دانلودها: {s.get('downloads', 0)}\n"
        f"میانگین امتیاز: {s.get('avg_score', 0.0):.1f}"
    )


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_primary_owner(user.id):
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
    if not is_primary_owner(user.id):
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
    if not is_primary_owner(user.id):
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
    if not is_primary_owner(user.id):
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
    if not is_primary_owner(user.id):
        return

    raw = " ".join(context.args).strip()
    if raw:
        if "|" not in raw:
            await update.message.reply_text(
                "فرمت درست نیست. مثال:\n"
                "/setcard 6037-xxxx-xxxx-xxxx | نام صاحب کارت"
            )
            return

        number, holder = [x.strip() for x in raw.split("|", 1)]
        set_setting(DEFAULT_CARD_NUMBER, number)
        set_setting(DEFAULT_CARD_HOLDER, holder)
        await update.message.reply_text("✅ اطلاعات کارت ذخیره شد.")
        return

    set_flow(context, "set_card_wait")
    await update.message.reply_text(
        "شماره کارت و نام صاحب کارت را با فرمت زیر ارسال کنید:\n"
        "6037-xxxx-xxxx-xxxx | نام صاحب کارت"
    )


async def feature_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_primary_owner(user.id):
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
    await update.message.reply_text(f"✅ {name} = {'on' if enabled else 'off'}")


async def setwelcome_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_primary_owner(user.id):
        return

    text = " ".join(context.args).strip()
    if text:
        set_setting("welcome_text", text)
        await update.message.reply_text("✅ متن خوش‌آمد ذخیره شد.")
        return

    set_flow(context, "set_welcome_wait")
    await update.message.reply_text("متن خوش‌آمد جدید را ارسال کنید.")


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not can_see_owner_panel(user.id):
        return

    card_number, card_holder = get_payment_card_info()
    current_welcome = get_setting("welcome_text") or WELCOME_TEXT
    await update.message.reply_text(
        "⚙ تنظیمات فعلی\n\n"
        f"شماره کارت: {card_number or 'ثبت نشده'}\n"
        f"صاحب کارت: {card_holder or 'ثبت نشده'}\n\n"
        f"متن خوش‌آمد:\n{current_welcome}\n\n"
        "دستورات:\n"
        "/setcard <number> | <holder>\n"
        "/setwelcome <text>\n"
        "/feature <name> on/off"
    )


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

    if not context.args:
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

    expire_date = (datetime.now() + timedelta(days=parse_duration_days(plan[3]))).strftime("%Y-%m-%d %H:%M:%S")
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
        parts = ticket_parts(row)
        if not parts:
            continue
        ticket_id, uid, username, message, status, admin_reply, created_at = parts
        short = message if len(str(message)) <= 40 else str(message)[:37] + "..."
        lines.append(f"#{ticket_id} | {uid} {username or ''} | {short}")

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

    parts = ticket_parts(ticket)
    if not parts:
        await update.message.reply_text("تیکت قابل خواندن نیست.")
        return

    ticket_id, uid, username, message, status, admin_reply, created_at = parts
    replies = get_replies(ticket_id)

    text = (
        f"🎫 تیکت #{ticket_id}\n"
        f"کاربر: {uid} {username or ''}\n"
        f"وضعیت: {status}\n"
        f"زمان: {created_at}\n\n"
        f"متن:\n{message}\n"
    )

    if admin_reply:
        text += f"\nپاسخ آخر:\n{admin_reply}\n"

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

    parts = ticket_parts(ticket)
    if not parts:
        await update.message.reply_text("تیکت قابل خواندن نیست.")
        return

    _, uid, username, _, status, _, _ = parts

    try:
        save_reply(ticket_id, user.id, message)
        close_ticket(ticket_id)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE tickets
            SET admin_reply = ?
            WHERE id = ?
            """,
            (message, ticket_id),
        )
        conn.commit()
        conn.close()

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
        parts = complaint_parts(row)
        if not parts:
            continue
        cid, uid, username, message, status, admin_reply, created_at = parts
        lines.append(f"#{cid} | {uid} {username or ''} | {message[:40]}")

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


async def addsong_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not can_manage_music(user.id):
        return

    set_flow(context, "add_song_file")
    await update.message.reply_text(
        "فایل آهنگ را ارسال کنید.\n"
        "فرمت: audio یا document"
    )


async def delsong_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not can_manage_music(user.id):
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
    if not can_manage_vpn(user.id):
        return

    set_flow(context, "add_plan_title")
    await update.message.reply_text("عنوان پلن را ارسال کنید.")


async def addserver_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not can_manage_vpn(user.id):
        return

    set_flow(context, "add_server_plan")
    await update.message.reply_text("شناسه پلن را ارسال کنید.")


async def addtest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not can_manage_vpn(user.id):
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


async def resettest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_primary_owner(user.id):
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
    if not is_primary_owner(user.id):
        return

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM vpn_test_users")
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ تست برای همه کاربران بازنشانی شد.")


async def complaint_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_feature_enabled("support_enabled", True) and not has_admin_access(user.id):
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
    if not is_feature_enabled("support_enabled", True) and not has_admin_access(user.id):
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


# -----------------------------
# Media handler
# -----------------------------

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
        clear_flow(context)
        await message.reply_text("❌ خطایی رخ داد.")


# -----------------------------
# Text handler
# -----------------------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()

    add_user(user.id, user.username, user.full_name)
    update_last_seen(user.id)
    ensure_wallet(user.id)

    if is_banned(user.id):
        await update.message.reply_text("⛔ حساب شما مسدود است.")
        return

    if is_spam(user.id):
        await update.message.reply_text("⛔ لطفاً کمی صبر کنید.")
        return

    flow = get_flow(context)
    state = flow.get(FLOW_STATE)

    try:
        # -------- active flows --------
        if state == "broadcast_wait":
            if not is_primary_owner(user.id):
                clear_flow(context)
                await update.message.reply_text("⛔ این بخش فقط برای مالک اصلی است.")
                return

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
            if not is_primary_owner(user.id):
                clear_flow(context)
                await update.message.reply_text("⛔ این بخش فقط برای مالک اصلی است.")
                return
            set_setting("welcome_text", text)
            clear_flow(context)
            await update.message.reply_text("✅ متن خوش‌آمد ذخیره شد.")
            return

        if state == "add_song_title":
            flow["title"] = text
            flow[FLOW_STATE] = "add_song_category"
            set_flow(context, **flow)
            await update.message.reply_text("دسته‌بندی را ارسال کنید یا از سبک‌های پیشنهادی استفاده کنید.")
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
            if not results:
                clear_flow(context)
                await update.message.reply_text("❌ آهنگی پیدا نشد.")
                return

            await show_song_list(
                update.message,
                context,
                results,
                f"🔍 نتایج جستجو برای «{keyword}»",
                page=0,
                mode="search",
                query_text=keyword,
            )
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
            if not is_primary_owner(user.id):
                clear_flow(context)
                await update.message.reply_text("⛔ این بخش فقط برای مالک اصلی است.")
                return

            if "|" not in text:
                await update.message.reply_text(
                    "فرمت درست نیست. مثال:\n"
                    "6037-xxxx-xxxx-xxxx | نام صاحب کارت"
                )
                return

            number, holder = [x.strip() for x in text.split("|", 1)]
            set_setting(DEFAULT_CARD_NUMBER, number)
            set_setting(DEFAULT_CARD_HOLDER, holder)
            clear_flow(context)
            await update.message.reply_text("✅ اطلاعات کارت ذخیره شد.")
            return

        # -------- main menu --------

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

        # -------- music section --------

        if text == "🎶 لیست آهنگ ها":
            if not is_feature_enabled("music_enabled", True) and not has_admin_access(user.id):
                await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
                return
            songs = get_all_songs()
            if not songs:
                await update.message.reply_text("فعلاً آهنگی ثبت نشده است.")
                return
            await show_song_list(update.message, context, songs, "🎶 لیست آهنگ‌ها", page=0, mode="all")
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
            await show_song_list(update.message, context, songs, "📈 آهنگ‌های ترند", page=0, mode="top")
            return

        if text == "🔍 جستجوی آهنگ":
            if not is_feature_enabled("music_enabled", True) and not has_admin_access(user.id):
                await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
                return
            set_flow(context, "search_song")
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

        # -------- vpn section --------

        if text == "💳 تعرفه سرورها":
            if not is_feature_enabled("vpn_enabled", True) and not has_admin_access(user.id):
                await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
                return
            plans = get_plans()
            if not plans:
                await update.message.reply_text("فعلاً تعرفه‌ای ثبت نشده است.")
                return
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
            set_flow(context, "wallet_topup_amount")
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
            set_flow(context, "ticket_wait")
            await update.message.reply_text("پیام پشتیبانی خود را ارسال کنید.")
            return

        if text == "🏢 سرویس سازمانی":
            if not is_feature_enabled("vpn_enabled", True) and not has_admin_access(user.id):
                await update.message.reply_text("این سرویس فعلاً غیرفعال است.")
                return
            set_flow(context, "corporate_wait")
            await update.message.reply_text("متن درخواست سازمانی را ارسال کنید.")
            return

        # -------- owner/admin area --------

        if text == "👮 مدیریت ادمین ها":
            if not is_primary_owner(user.id):
                await update.message.reply_text("⛔ این بخش فقط برای مالک اصلی است.")
                return
            await update.message.reply_text(
                "مدیریت ادمین‌ها:\n\n"
                "/addadmin <id> <vpn/music/support/temp>\n"
                "/removeadmin <id>\n"
                "/admins"
            )
            return

        if text == "📢 پیام همگانی":
            if not is_primary_owner(user.id):
                await update.message.reply_text("⛔ این بخش فقط برای مالک اصلی است.")
                return
            set_flow(context, "broadcast_wait")
            await update.message.reply_text("متن پیام همگانی را ارسال کنید.")
            return

        if text == "⚙ تنظیمات":
            if not can_see_owner_panel(user.id):
                return
            await settings_cmd(update, context)
            return

        if text == "📊 آمار کامل":
            await stats_cmd(update, context)
            return

        if text == "📊 آمار کاربران":
            await stats_cmd(update, context)
            return

        if text == "💰 بررسی پرداخت ها":
            await pendingpayments_view_cmd(update, context)
            return

        if text == "🎫 تیکت ها":
            await pendingtickets_cmd(update, context)
            return

        if text == "🌐 سرورها":
            if not can_manage_vpn(user.id):
                await update.message.reply_text("⛔ این بخش فقط برای ادمین VPN یا مالک است.")
                return
            plans = get_plans()
            if not plans:
                await update.message.reply_text("تعرفه‌ای ثبت نشده است.")
                return
            await show_plan_list(update.message, context, plans, "🌐 تعرفه و سرورها", 0)
            return

        if text == "🎵 مدیریت موزیک":
            if not can_manage_music(user.id):
                await update.message.reply_text("⛔ این بخش فقط برای ادمین موزیک یا مالک است.")
                return
            await update.message.reply_text(
                "🎵 مدیریت موزیک:\n"
                "/addsong\n"
                "/delsong <id>\n"
                "/songstats"
            )
            return

        if text == "🔙 بازگشت":
            clear_flow(context)
            await update.message.reply_text("منوی اصلی:", reply_markup=main_menu())
            return

        await update.message.reply_text("از منوی ربات استفاده کنید.")

    except Exception as e:
        log_error(e)
        clear_flow(context)
        await update.message.reply_text("❌ خطایی رخ داد.")


# -----------------------------
# Callback handler
# -----------------------------

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if is_banned(user.id):
        await query.edit_message_text("⛔ حساب شما مسدود است.")
        return

    data = query.data or ""

    try:
        # ---- song paging ----
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
            page = clamp_page(page, len(songs), PAGE_SIZE_SONGS)
            title_map = {
                "all": "🎶 لیست آهنگ‌ها",
                "new": "🆕 جدیدترین آهنگ‌ها",
                "top": "⭐ محبوب‌ترین آهنگ‌ها",
                "search": f"🔍 نتایج جستجو برای «{flow.get('query', '')}»",
                "category": f"📂 آهنگ‌های سبک «{flow.get('category', '')}»",
            }
            title = title_map.get(mode, "🎶 لیست آهنگ‌ها")
            await edit_song_list(
                query,
                context,
                songs,
                title,
                page=page,
                mode=mode,
                query_text=flow.get("query", ""),
                category=flow.get("category", ""),
            )
            return

        if data.startswith("songkind:"):
            kind = data.split(":", 1)[1]
            if kind == "new":
                songs = get_new_songs(50)
                if not songs:
                    await query.edit_message_text("فعلاً آهنگی ثبت نشده است.")
                    return
                set_flow(context, "song_view", mode="new", page=0)
                await edit_song_list(query, context, songs, "🆕 جدیدترین آهنگ‌ها", page=0, mode="new")
                return
            if kind == "top":
                songs = get_top_songs(50)
                if not songs:
                    await query.edit_message_text("فعلاً آهنگی ثبت نشده است.")
                    return
                set_flow(context, "song_view", mode="top", page=0)
                await edit_song_list(query, context, songs, "⭐ محبوب‌ترین آهنگ‌ها", page=0, mode="top")
                return

        if data.startswith("song_open:"):
            song_id = parse_int(data.split(":", 1)[1])
            song = get_song(song_id)
            if not song:
                await query.edit_message_text("آهنگ پیدا نشد.")
                return
            await send_song_media(context, user.id, song)
            return

        if data.startswith("rate:"):
            _, song_id, score = data.split(":", 2)
            song_id = parse_int(song_id)
            score = parse_int(score, 1) or 1
            add_song_score(song_id, score)
            await query.answer(f"⭐ امتیاز {score} ثبت شد.")
            return

        if data == "songback:main":
            clear_flow(context)
            await send_menu(context, user.id, "منوی اصلی:", main_menu())
            return

        if data == "random:any":
            song = get_random_song()
            if not song:
                await query.edit_message_text("فعلاً آهنگی ثبت نشده است.")
                return
            await send_song_media(context, user.id, song)
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
            await send_song_media(context, user.id, song)
            return

        # ---- plan paging / open ----
        if data.startswith("planpage:"):
            direction = data.split(":", 1)[1]
            page = int(context.user_data.get("plan_view", {}).get("page", 0))
            if direction == "next":
                page += 1
            elif direction == "prev":
                page = max(0, page - 1)
            plans = get_plans()
            page = clamp_page(page, len(plans), PAGE_SIZE_PLANS)
            await edit_plan_list(query, context, plans, "💳 تعرفه سرورها", page=page)
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
                keyboard.append([
                    InlineKeyboardButton(
                        f"{server_name} | {location}",
                        callback_data=f"server_open:{server_id}",
                    )
                ])
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="planback:list")])

            text = plan_caption(plan) + "\n\nسرورهای موجود را انتخاب کنید."
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
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("💰 پرداخت از کیف پول", callback_data=f"server_pay_wallet:{server_id}"),
                        InlineKeyboardButton("💳 پرداخت مستقیم", callback_data=f"server_pay_direct:{server_id}"),
                    ],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="planback:list")],
                ]
            )
            await query.edit_message_text(text, reply_markup=keyboard)
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

            expire_date = (datetime.now() + timedelta(days=parse_duration_days(plan[3]))).strftime("%Y-%m-%d %H:%M:%S")
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

        if data == "planback:list":
            plans = get_plans()
            page = int(context.user_data.get("plan_view", {}).get("page", 0))
            page = clamp_page(page, len(plans), PAGE_SIZE_PLANS)
            await edit_plan_list(query, context, plans, "💳 تعرفه سرورها", page=page)
            return

        # ---- payments ----
        if data.startswith("pay_open:"):
            pay_id = parse_int(data.split(":", 1)[1])
            payment = get_payment(pay_id)
            if not payment:
                await query.edit_message_text("پرداخت پیدا نشد.")
                return

            pay_id, uid, amount, receipt_file_id, status, reviewed_at, created_at = payment
            kind, raw_id = file_kind_and_id(receipt_file_id)
            caption = (
                f"💳 پرداخت جدید #{pay_id}\n"
                f"کاربر: {uid}\n"
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
                        chat_id=user.id,
                        photo=raw_id,
                        caption=caption,
                        reply_markup=keyboard,
                    )
                else:
                    await context.bot.send_document(
                        chat_id=user.id,
                        document=raw_id,
                        caption=caption,
                        reply_markup=keyboard,
                    )
            except Exception:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=caption,
                    reply_markup=keyboard,
                )
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

        # ---- back buttons ----
        if data == "songback:main":
            clear_flow(context)
            await send_menu(context, user.id, "منوی اصلی:", main_menu())
            return

        if data == "randback:music":
            clear_flow(context)
            await send_menu(context, user.id, "🎵 بخش موزیک:", music_menu())
            return

    except Exception as e:
        log_error(e)
        try:
            await query.edit_message_text("❌ خطا رخ داد.")
        except Exception:
            pass


async def error_handler(update, context):
    try:
        log_error(context.error)
    except Exception:
        pass


def main():
    init_database()
    ensure_compat_schema()
    bootstrap_owner()

    token = TOKEN
    if not token:
        print("BOT_TOKEN تنظیم نشده است")
        return

    app = Application.builder().token(token).build()

    # commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("owner", owner_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("songstats", songstats_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("addadmin", addadmin_cmd))
    app.add_handler(CommandHandler("removeadmin", removeadmin_cmd))
    app.add_handler(CommandHandler("admins", admins_cmd))
    app.add_handler(CommandHandler("setcard", setcard_cmd))
    app.add_handler(CommandHandler("feature", feature_cmd))
    app.add_handler(CommandHandler("setwelcome", setwelcome_cmd))
    app.add_handler(CommandHandler("settings", settings_cmd))

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

    app.add_handler(CommandHandler("ticket", ticket_cmd))
    app.add_handler(CommandHandler("complaint", complaint_cmd))

    # callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # media and text
    app.add_handler(MessageHandler(filters.PHOTO | filters.AUDIO | filters.Document.ALL, handle_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.add_error_handler(error_handler)

    log_info("Bot4 started")
    print("Bot4 started")
    app.run_polling()


if __name__ == "__main__":
    main()
