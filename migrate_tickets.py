from database import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute(
    """
    DROP TABLE IF EXISTS tickets
    """
)

cur.execute(
    """
    CREATE TABLE tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        message TEXT,
        status TEXT DEFAULT 'open',
        created_at TEXT
    )
    """
)

conn.commit()
conn.close()

print("tickets recreated")
