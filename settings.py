from database import get_connection


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
        (name, str(value))
    )

    conn.commit()
    conn.close()


def get_setting(name):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT value
        FROM settings
        WHERE name = ?
        """,
        (name,)
    )

    row = cur.fetchone()
    conn.close()

    return row[0] if row else None


def get_all_settings():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT name, value
        FROM settings
        ORDER BY name ASC
        """
    )

    rows = cur.fetchall()
    conn.close()
    return rows
