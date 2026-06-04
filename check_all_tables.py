from database import get_connection

conn = get_connection()
cur = conn.cursor()

tables = [
    "users",
    "wallets",
    "roles",
    "tickets",
    "songs"
]

for table in tables:

    print("\n======")
    print(table)
    print("======")

    try:

        cur.execute(
            f"PRAGMA table_info({table})"
        )

        for row in cur.fetchall():
            print(row)

    except Exception as e:
        print(e)

conn.close()
