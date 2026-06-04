from datetime import datetime
from database import get_connection


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add_user(telegram_id, username=None, full_name=None):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO users (
            telegram_id,
            username,
            full_name,
            join_date,
            last_seen,
            is_banned
        )
        VALUES (?, ?, ?, ?, ?, 0)
        """,
        (
            int(telegram_id),
            username,
            full_name,
            datetime.now().strftime("%Y-%m-%d"),
            _now(),
        )
    )

    cur.execute(
        """
        UPDATE users
        SET
            username = COALESCE(?, username),
            full_name = COALESCE(?, full_name),
            last_seen = ?
        WHERE telegram_id = ?
        """,
        (
            username,
            full_name,
            _now(),
            int(telegram_id),
        )
    )

    conn.commit()
    conn.close()


def update_last_seen(telegram_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET last_seen = ?
        WHERE telegram_id = ?
        """,
        (_now(), int(telegram_id))
    )

    conn.commit()
    conn.close()


def get_user(telegram_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, telegram_id, username, full_name, join_date, last_seen, is_banned
        FROM users
        WHERE telegram_id = ?
        """,
        (int(telegram_id),)
    )

    row = cur.fetchone()
    conn.close()
    return row


def get_all_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, telegram_id, username, full_name, join_date, last_seen, is_banned
        FROM users
        ORDER BY id DESC
        """
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def count_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]

    conn.close()
    return total


def count_today_users():
    conn = get_connection()
    cur = conn.cursor()

    today = datetime.now().strftime("%Y-%m-%d")

    cur.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE join_date = ?
        """,
        (today,)
    )

    total = cur.fetchone()[0]
    conn.close()
    return total


def ban_user(telegram_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET is_banned = 1
        WHERE telegram_id = ?
        """,
        (int(telegram_id),)
    )

    conn.commit()
    conn.close()


def unban_user(telegram_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET is_banned = 0
        WHERE telegram_id = ?
        """,
        (int(telegram_id),)
    )

    conn.commit()
    conn.close()


def is_banned(telegram_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT is_banned
        FROM users
        WHERE telegram_id = ?
        """,
        (int(telegram_id),)
    )

    row = cur.fetchone()
    conn.close()

    if not row:
        return False

    return bool(row[0])
