from datetime import datetime
from database import get_connection


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _ensure_row(telegram_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id
        FROM roles
        WHERE telegram_id = ?
        """,
        (telegram_id,)
    )
    row = cur.fetchone()

    if row is None:
        cur.execute(
            """
            INSERT INTO roles (
                telegram_id,
                is_owner,
                is_temp_owner,
                is_vpn_admin,
                is_music_admin,
                is_support_admin,
                created_at
            )
            VALUES (?, 0, 0, 0, 0, 0, ?)
            """,
            (telegram_id, _now())
        )
        conn.commit()

    conn.close()


def set_owner(telegram_id, value=True):
    _ensure_row(telegram_id)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE roles
        SET is_owner = ?
        WHERE telegram_id = ?
        """,
        (1 if value else 0, telegram_id)
    )

    conn.commit()
    conn.close()


def set_temp_owner(telegram_id, value=True):
    _ensure_row(telegram_id)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE roles
        SET is_temp_owner = ?
        WHERE telegram_id = ?
        """,
        (1 if value else 0, telegram_id)
    )

    conn.commit()
    conn.close()


def set_vpn_admin(telegram_id, value=True):
    _ensure_row(telegram_id)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE roles
        SET is_vpn_admin = ?
        WHERE telegram_id = ?
        """,
        (1 if value else 0, telegram_id)
    )

    conn.commit()
    conn.close()


def set_music_admin(telegram_id, value=True):
    _ensure_row(telegram_id)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE roles
        SET is_music_admin = ?
        WHERE telegram_id = ?
        """,
        (1 if value else 0, telegram_id)
    )

    conn.commit()
    conn.close()


def set_support_admin(telegram_id, value=True):
    _ensure_row(telegram_id)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE roles
        SET is_support_admin = ?
        WHERE telegram_id = ?
        """,
        (1 if value else 0, telegram_id)
    )

    conn.commit()
    conn.close()


def clear_all_roles(telegram_id):
    _ensure_row(telegram_id)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE roles
        SET is_owner = 0,
            is_temp_owner = 0,
            is_vpn_admin = 0,
            is_music_admin = 0,
            is_support_admin = 0
        WHERE telegram_id = ?
        """,
        (telegram_id,)
    )

    conn.commit()
    conn.close()


def get_roles(telegram_id):
    _ensure_row(telegram_id)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            is_owner,
            is_temp_owner,
            is_vpn_admin,
            is_music_admin,
            is_support_admin
        FROM roles
        WHERE telegram_id = ?
        """,
        (telegram_id,)
    )

    row = cur.fetchone()
    conn.close()

    if not row:
        return {
            "owner": False,
            "temp_owner": False,
            "vpn_admin": False,
            "music_admin": False,
            "support_admin": False,
        }

    return {
        "owner": bool(row[0]),
        "temp_owner": bool(row[1]),
        "vpn_admin": bool(row[2]),
        "music_admin": bool(row[3]),
        "support_admin": bool(row[4]),
    }


def is_owner(telegram_id):
    return get_roles(telegram_id)["owner"]


def is_temp_owner(telegram_id):
    return get_roles(telegram_id)["temp_owner"]


def is_vpn_admin(telegram_id):
    return get_roles(telegram_id)["vpn_admin"]


def is_music_admin(telegram_id):
    return get_roles(telegram_id)["music_admin"]


def is_support_admin(telegram_id):
    return get_roles(telegram_id)["support_admin"]


def has_any_admin_role(telegram_id):
    roles = get_roles(telegram_id)
    return (
        roles["owner"]
        or roles["temp_owner"]
        or roles["vpn_admin"]
        or roles["music_admin"]
        or roles["support_admin"]
    )


def get_role_label(telegram_id):
    roles = get_roles(telegram_id)

    if roles["owner"]:
        return "owner"
    if roles["temp_owner"]:
        return "temp_owner"
    if roles["vpn_admin"]:
        return "vpn_admin"
    if roles["music_admin"]:
        return "music_admin"
    if roles["support_admin"]:
        return "support_admin"
    return "user"


def list_all_roles():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            telegram_id,
            is_owner,
            is_temp_owner,
            is_vpn_admin,
            is_music_admin,
            is_support_admin,
            created_at
        FROM roles
        ORDER BY created_at DESC
        """
    )

    rows = cur.fetchall()
    conn.close()
    return rows
