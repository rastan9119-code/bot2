from database import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS payments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    receipt_file_id TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    reviewed_at TEXT
)
""")

conn.commit()
conn.close()

print("PAYMENTS TABLE CREATED")
