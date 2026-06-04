from database import get_connection

conn = get_connection()
cur = conn.cursor()

# تعرفه ها
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

# سرورها
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

# سرویس های اختصاص یافته
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

# تست
cur.execute("""
CREATE TABLE IF NOT EXISTS vpn_test(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_text TEXT,
    is_active INTEGER DEFAULT 1
)
""")

# دریافت تست توسط کاربر
cur.execute("""
CREATE TABLE IF NOT EXISTS vpn_test_users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    received_at TEXT
)
""")

conn.commit()
conn.close()

print("VPN TABLES CREATED")
