from datetime import datetime
from database import get_connection


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_wallet(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id
        FROM wallets
        WHERE user_id = ?
        """,
        (user_id,)
    )
    row = cur.fetchone()

    if row is None:
        cur.execute(
            """
            INSERT INTO wallets (
                user_id,
                balance,
                updated_at
            )
            VALUES (?, 0, ?)
            """,
            (user_id, _now())
        )
        conn.commit()

    conn.close()


def get_balance(user_id):
    ensure_wallet(user_id)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT balance
        FROM wallets
        WHERE user_id = ?
        """,
        (user_id,)
    )
    row = cur.fetchone()
    conn.close()

    return int(row[0]) if row else 0


def set_balance(user_id, amount):
    ensure_wallet(user_id)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE wallets
        SET balance = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (int(amount), _now(), user_id)
    )

    conn.commit()
    conn.close()


def add_balance(user_id, amount, note=""):
    amount = int(amount)
    current = get_balance(user_id)
    new_balance = current + amount

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE wallets
        SET balance = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (new_balance, _now(), user_id)
    )

    cur.execute(
        """
        INSERT INTO wallet_transactions (
            user_id,
            amount,
            tx_type,
            status,
            note,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, amount, "credit", "approved", note, _now())
    )

    conn.commit()
    conn.close()

    return new_balance


def subtract_balance(user_id, amount, note=""):
    amount = int(amount)
    current = get_balance(user_id)

    if current < amount:
        return False, current

    new_balance = current - amount

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE wallets
        SET balance = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (new_balance, _now(), user_id)
    )

    cur.execute(
        """
        INSERT INTO wallet_transactions (
            user_id,
            amount,
            tx_type,
            status,
            note,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, amount, "debit", "approved", note, _now())
    )

    conn.commit()
    conn.close()

    return True, new_balance


def add_topup_request(user_id, amount, receipt_file_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO topup_requests (
            user_id,
            amount,
            receipt_file_id,
            status,
            created_at
        )
        VALUES (?, ?, ?, 'pending', ?)
        """,
        (user_id, int(amount), receipt_file_id, _now())
    )

    cur.execute(
        """
        INSERT INTO wallet_transactions (
            user_id,
            amount,
            tx_type,
            status,
            note,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, int(amount), "topup_request", "pending", "receipt_uploaded", _now())
    )

    conn.commit()
    conn.close()


def get_pending_topups():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, amount, receipt_file_id, status, created_at
        FROM topup_requests
        WHERE status = 'pending'
        ORDER BY id DESC
        """
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def get_topup_request(request_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, amount, receipt_file_id, status, created_at
        FROM topup_requests
        WHERE id = ?
        """,
        (request_id,)
    )

    row = cur.fetchone()
    conn.close()
    return row


def approve_topup(request_id, admin_note=""):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT user_id, amount, status
        FROM topup_requests
        WHERE id = ?
        """,
        (request_id,)
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        return False, None, None

    user_id, amount, status = row
    if status != "pending":
        conn.close()
        return False, user_id, amount

    ensure_wallet(user_id)

    cur.execute(
        """
        UPDATE wallets
        SET balance = balance + ?, updated_at = ?
        WHERE user_id = ?
        """,
        (int(amount), _now(), user_id)
    )

    cur.execute(
        """
        UPDATE topup_requests
        SET status = 'approved', admin_note = ?
        WHERE id = ?
        """,
        (admin_note, request_id)
    )

    cur.execute(
        """
        INSERT INTO wallet_transactions (
            user_id,
            amount,
            tx_type,
            status,
            note,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, int(amount), "credit", "approved", f"topup_request:{request_id}", _now())
    )

    conn.commit()
    conn.close()

    return True, user_id, amount


def reject_topup(request_id, admin_note=""):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT user_id, amount, status
        FROM topup_requests
        WHERE id = ?
        """,
        (request_id,)
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        return False, None, None

    user_id, amount, status = row
    if status != "pending":
        conn.close()
        return False, user_id, amount

    cur.execute(
        """
        UPDATE topup_requests
        SET status = 'rejected', admin_note = ?
        WHERE id = ?
        """,
        (admin_note, request_id)
    )

    cur.execute(
        """
        INSERT INTO wallet_transactions (
            user_id,
            amount,
            tx_type,
            status,
            note,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, int(amount), "topup_request", "rejected", f"topup_request:{request_id}", _now())
    )

    conn.commit()
    conn.close()

    return True, user_id, amount


def get_wallet_transactions(user_id, limit=20):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, amount, tx_type, status, note, created_at
        FROM wallet_transactions
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, int(limit))
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def format_balance(user_id):
    return f"{get_balance(user_id):,} تومان"
