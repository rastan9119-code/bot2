from database import get_connection
from datetime import datetime


def get_stats():

    conn = get_connection()
    cur = conn.cursor()

    stats = {}

    # users

    cur.execute(
        "SELECT COUNT(*) FROM users"
    )

    stats["users"] = cur.fetchone()[0]

    # today users

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    cur.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE join_date LIKE ?
        """,
        (f"{today}%",)
    )

    stats["today_users"] = (
        cur.fetchone()[0]
    )

    # songs

    try:

        cur.execute(
            """
            SELECT COUNT(*)
            FROM songs
            """
        )

        stats["songs"] = (
            cur.fetchone()[0]
        )

    except:
        stats["songs"] = 0

    # tickets

    try:

        cur.execute(
            """
            SELECT COUNT(*)
            FROM tickets
            """
        )

        stats["tickets"] = (
            cur.fetchone()[0]
        )

    except:
        stats["tickets"] = 0

    # vpn plans

    try:

        cur.execute(
            """
            SELECT COUNT(*)
            FROM vpn_plans
            """
        )

        stats["vpn_plans"] = (
            cur.fetchone()[0]
        )

    except:
        stats["vpn_plans"] = 0

    # vpn servers

    try:

        cur.execute(
            """
            SELECT COUNT(*)
            FROM vpn_servers
            """
        )

        stats["vpn_servers"] = (
            cur.fetchone()[0]
        )

    except:
        stats["vpn_servers"] = 0

    # payments

    try:

        cur.execute(
            """
            SELECT COUNT(*)
            FROM payments
            """
        )

        stats["payments"] = (
            cur.fetchone()[0]
        )

    except:
        stats["payments"] = 0

    # wallet balance

    try:

        cur.execute(
            """
            SELECT SUM(balance)
            FROM wallets
            """
        )

        result = cur.fetchone()[0]

        stats["wallet_total"] = (
            result if result else 0
        )

    except:
        stats["wallet_total"] = 0

    conn.close()

    return stats
