from database import get_connection

conn = get_connection()
cur = conn.cursor()

cur.execute(
    "PRAGMA table_info(payments)"
)

for row in cur.fetchall():
    print(row)

conn.close()
