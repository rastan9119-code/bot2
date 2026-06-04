import sqlite3
from config import DATABASE_NAME


def get_connection():
    return sqlite3.connect(DATABASE_NAME)


def init_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        username TEXT,
        full_name TEXT,
        join_date TEXT,
        last_seen TEXT,
        is_banned INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS roles(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        is_owner INTEGER DEFAULT 0,
        is_temp_owner INTEGER DEFAULT 0,
        is_vpn_admin INTEGER DEFAULT 0,
        is_music_admin INTEGER DEFAULT 0,
        is_support_admin INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS songs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        file_id TEXT,
        category TEXT,
        score REAL DEFAULT 0,
        downloads INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS song_categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        is_active INTEGER DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS song_favorites(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        song_id INTEGER,
        created_at TEXT,
        UNIQUE(user_id, song_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS wallets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        balance INTEGER DEFAULT 0,
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS wallet_transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        tx_type TEXT,
        status TEXT,
        note TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS topup_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        receipt_file_id TEXT,
        status TEXT DEFAULT 'pending',
        admin_note TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS receipts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        file_id TEXT,
        amount INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )
    """)

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
    CREATE TABLE IF NOT EXISTS vps_plans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        volume TEXT,
        duration TEXT,
        price INTEGER,
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
    CREATE TABLE IF NOT EXISTS vps_servers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER,
        name TEXT,
        location TEXT,
        volume TEXT,
        duration TEXT,
        price INTEGER,
        server_data TEXT,
        is_test INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
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
    CREATE TABLE IF NOT EXISTS test_access(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        used_count INTEGER DEFAULT 0,
        reset_allowed INTEGER DEFAULT 0,
        updated_at TEXT
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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS complaints(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        message TEXT,
        status TEXT DEFAULT 'open',
        admin_reply TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tickets(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        message TEXT,
        status TEXT DEFAULT 'open',
        admin_reply TEXT,
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
    CREATE TABLE IF NOT EXISTS settings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        value TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS feature_flags(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        is_enabled INTEGER DEFAULT 1,
        note TEXT,
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS scheduled_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT,
        send_time TEXT,
        is_sent INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS activity_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        action TEXT,
        details TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()
