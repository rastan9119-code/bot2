from datetime import datetime
from database import get_connection


def now():
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# =====================
# PLANS
# =====================

def add_plan(
    title,
    volume,
    duration,
    price
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO vpn_plans
        (
            title,
            volume,
            duration,
            price,
            created_at
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?
        )
        """,
        (
            title,
            volume,
            duration,
            price,
            now()
        )
    )

    conn.commit()
    conn.close()


def get_plans():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM vpn_plans
        ORDER BY id ASC
        """
    )

    result = cur.fetchall()

    conn.close()

    return result


def get_plan(
    plan_id
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM vpn_plans
        WHERE id=?
        """,
        (plan_id,)
    )

    result = cur.fetchone()

    conn.close()

    return result


# =====================
# SERVERS
# =====================

def add_server(
    plan_id,
    server_name,
    location,
    config_text
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO vpn_servers
        (
            plan_id,
            server_name,
            location,
            config_text,
            created_at
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?
        )
        """,
        (
            plan_id,
            server_name,
            location,
            config_text,
            now()
        )
    )

    conn.commit()
    conn.close()


def get_servers(
    plan_id
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM vpn_servers
        WHERE plan_id=?
        AND is_used=0
        ORDER BY id ASC
        """,
        (plan_id,)
    )

    result = cur.fetchall()

    conn.close()

    return result


def get_server(
    server_id
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM vpn_servers
        WHERE id=?
        """,
        (server_id,)
    )

    result = cur.fetchone()

    conn.close()

    return result


# =====================
# ASSIGN SERVER
# =====================

def assign_server(
    user_id,
    server_id,
    expire_date
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO user_vpn
        (
            user_id,
            server_id,
            assigned_at,
            expire_date
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?
        )
        """,
        (
            user_id,
            server_id,
            now(),
            expire_date
        )
    )

    cur.execute(
        """
        UPDATE vpn_servers
        SET is_used=1
        WHERE id=?
        """,
        (server_id,)
    )

    conn.commit()
    conn.close()


def get_user_servers(
    user_id
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM user_vpn
        WHERE user_id=?
        ORDER BY id DESC
        """,
        (user_id,)
    )

    result = cur.fetchall()

    conn.close()

    return result

# =====================
# TEST SERVER
# =====================

def add_test_server(config_text):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO vps_servers
        (
            plan_id,
            name,
            location,
            volume,
            duration,
            price,
            server_data,
            is_test,
            is_active,
            created_at
        )
        VALUES
        (
            0,
            'TEST',
            'TEST',
            'TEST',
            'TEST',
            0,
            ?,
            1,
            1,
            ?
        )
        """,
        (
            config_text,
            now()
        )
    )

    conn.commit()
    conn.close()


def get_test_server():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM vps_servers
        WHERE is_test = 1
        AND is_active = 1
        ORDER BY id DESC
        LIMIT 1
        """
    )

    result = cur.fetchone()

    conn.close()

    return result


def user_received_test(user_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT used_count
        FROM test_access
        WHERE user_id = ?
        """,
        (user_id,)
    )

    row = cur.fetchone()

    conn.close()

    if not row:
        return False

    return row[0] > 0


def mark_test_received(user_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id
        FROM test_access
        WHERE user_id = ?
        """,
        (user_id,)
    )

    row = cur.fetchone()

    if row:

        cur.execute(
            """
            UPDATE test_access
            SET used_count = used_count + 1,
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                now(),
                user_id
            )
        )

    else:

        cur.execute(
            """
            INSERT INTO test_access
            (
                user_id,
                used_count,
                reset_allowed,
                updated_at
            )
            VALUES
            (
                ?,
                1,
                0,
                ?
            )
            """,
            (
                user_id,
                now()
            )
        )

    conn.commit()
    conn.close()


def reset_test_user(user_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE test_access
        SET used_count = 0,
            reset_allowed = 1,
            updated_at = ?
        WHERE user_id = ?
        """,
        (
            now(),
            user_id
        )
    )

    conn.commit()
    conn.close()


def reset_all_test_users():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE test_access
        SET used_count = 0,
            reset_allowed = 1,
            updated_at = ?
        """,
        (
            now(),
        )
    )

    conn.commit()
    conn.close()
