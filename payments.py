from datetime import datetime

from database import get_connection
from wallet import add_balance


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_payment(user_id, amount, receipt_file_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO payments
        (
            user_id,
            amount,
            receipt_file_id,
            status,
            created_at
        )
        VALUES
        (
            ?,
            ?,
            ?,
            'pending',
            ?
        )
        """,
        (
            user_id,
            int(amount),
            receipt_file_id,
            now()
        )
    )

    conn.commit()
    conn.close()


def get_pending_payments():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, amount, receipt_file_id, status, reviewed_at, created_at
        FROM payments
        WHERE status = 'pending'
        ORDER BY id DESC
        """
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def get_payment(payment_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_id, amount, receipt_file_id, status, reviewed_at, created_at
        FROM payments
        WHERE id = ?
        """,
        (int(payment_id),)
    )

    row = cur.fetchone()
    conn.close()
    return row


def approve_payment(payment_id):
    payment = get_payment(payment_id)
    if not payment:
        return False

    pay_id, user_id, amount, receipt_file_id, status, reviewed_at, created_at = payment
    if status != "pending":
        return False

    add_balance(user_id, int(amount), f"payment #{payment_id}")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE payments
        SET status = 'approved',
            reviewed_at = ?
        WHERE id = ?
        """,
        (now(), int(payment_id))
    )

    conn.commit()
    conn.close()
    return True


def reject_payment(payment_id):
    payment = get_payment(payment_id)
    if not payment:
        return False

    pay_id, user_id, amount, receipt_file_id, status, reviewed_at, created_at = payment
    if status != "pending":
        return False

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE payments
        SET status = 'rejected',
            reviewed_at = ?
        WHERE id = ?
        """,
        (now(), int(payment_id))
    )

    conn.commit()
    conn.close()
    return True
