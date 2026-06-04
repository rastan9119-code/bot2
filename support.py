from datetime import datetime
from database import get_connection


def now():
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ------------------
# COMPLAINTS
# ------------------

def create_complaint(
    user_id,
    username,
    message
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO complaints
        (
            user_id,
            username,
            message,
            status,
            created_at
        )
        VALUES
        (
            ?,
            ?,
            ?,
            'open',
            ?
        )
        """,
        (
            user_id,
            username,
            message,
            now()
        )
    )

    conn.commit()
    conn.close()


def get_open_complaints():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM complaints
        WHERE status='open'
        ORDER BY id DESC
        """
    )

    result = cur.fetchall()

    conn.close()

    return result


def close_complaint(
    complaint_id
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE complaints
        SET status='closed'
        WHERE id=?
        """,
        (complaint_id,)
    )

    conn.commit()
    conn.close()


# ------------------
# TICKETS
# ------------------

def create_ticket(
    user_id,
    username,
    message
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO tickets
        (
            user_id,
            username,
            message,
            status,
            created_at
        )
        VALUES
        (
            ?,
            ?,
            ?,
            'open',
            ?
        )
        """,
        (
            user_id,
            username,
            message,
            now()
        )
    )

    conn.commit()
    conn.close()


def get_open_tickets():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM tickets
        WHERE status='open'
        ORDER BY id DESC
        """
    )

    result = cur.fetchall()

    conn.close()

    return result


def get_ticket(
    ticket_id
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM tickets
        WHERE id=?
        """,
        (ticket_id,)
    )

    result = cur.fetchone()

    conn.close()

    return result


def close_ticket(
    ticket_id
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE tickets
        SET status='closed'
        WHERE id=?
        """,
        (ticket_id,)
    )

    conn.commit()
    conn.close()


# ------------------
# ADMIN REPLY
# ------------------

def save_reply(
    ticket_id,
    admin_id,
    message
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO replies
        (
            ticket_id,
            admin_id,
            message,
            created_at
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
            ticket_id,
            admin_id,
            message,
            now()
        )
    )

    conn.commit()
    conn.close()


def get_replies(
    ticket_id
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM replies
        WHERE ticket_id=?
        ORDER BY id ASC
        """,
        (ticket_id,)
    )

    result = cur.fetchall()

    conn.close()

    return result
