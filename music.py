from datetime import datetime
import random

from database import get_connection


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add_song(title, file_id, category, score=0.0, is_active=1):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO songs (
            title,
            file_id,
            category,
            score,
            downloads,
            is_active,
            created_at
        )
        VALUES (?, ?, ?, ?, 0, ?, ?)
        """,
        (
            title,
            file_id,
            category,
            float(score),
            int(is_active),
            _now(),
        )
    )

    conn.commit()
    conn.close()


def delete_song(song_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM songs
        WHERE id = ?
        """,
        (int(song_id),)
    )

    conn.commit()
    conn.close()


def set_song_active(song_id, is_active=True):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE songs
        SET is_active = ?
        WHERE id = ?
        """,
        (1 if is_active else 0, int(song_id))
    )

    conn.commit()
    conn.close()


def update_song(song_id, title=None, file_id=None, category=None, score=None):
    conn = get_connection()
    cur = conn.cursor()

    song = get_song(song_id)
    if not song:
        conn.close()
        return False

    new_title = title if title is not None else song[1]
    new_file_id = file_id if file_id is not None else song[2]
    new_category = category if category is not None else song[3]
    new_score = float(score) if score is not None else float(song[4])

    cur.execute(
        """
        UPDATE songs
        SET title = ?,
            file_id = ?,
            category = ?,
            score = ?
        WHERE id = ?
        """,
        (
            new_title,
            new_file_id,
            new_category,
            new_score,
            int(song_id),
        )
    )

    conn.commit()
    conn.close()
    return True


def get_song(song_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, title, file_id, category, score, downloads, is_active, created_at
        FROM songs
        WHERE id = ?
        """,
        (int(song_id),)
    )

    row = cur.fetchone()
    conn.close()
    return row


def get_all_songs(limit=None):
    conn = get_connection()
    cur = conn.cursor()

    if limit is None:
        cur.execute(
            """
            SELECT id, title, file_id, category, score, downloads, is_active, created_at
            FROM songs
            WHERE is_active = 1
            ORDER BY id DESC
            """
        )
    else:
        cur.execute(
            """
            SELECT id, title, file_id, category, score, downloads, is_active, created_at
            FROM songs
            WHERE is_active = 1
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),)
        )

    rows = cur.fetchall()
    conn.close()
    return rows


def get_new_songs(limit=10):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, title, file_id, category, score, downloads, is_active, created_at
        FROM songs
        WHERE is_active = 1
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limit),)
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def get_top_songs(limit=10):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, title, file_id, category, score, downloads, is_active, created_at
        FROM songs
        WHERE is_active = 1
        ORDER BY downloads DESC, score DESC, id DESC
        LIMIT ?
        """,
        (int(limit),)
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def search_song(keyword):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, title, file_id, category, score, downloads, is_active, created_at
        FROM songs
        WHERE is_active = 1
          AND (
              title LIKE ?
              OR category LIKE ?
          )
        ORDER BY downloads DESC, score DESC, id DESC
        """,
        (f"%{keyword}%", f"%{keyword}%")
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def get_category_songs(category):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, title, file_id, category, score, downloads, is_active, created_at
        FROM songs
        WHERE is_active = 1
          AND category = ?
        ORDER BY downloads DESC, score DESC, id DESC
        """,
        (category,)
    )

    rows = cur.fetchall()
    conn.close()
    return rows


def get_categories():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT DISTINCT category
        FROM songs
        WHERE is_active = 1
          AND category IS NOT NULL
          AND category != ''
        ORDER BY category ASC
        """
    )

    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_random_song():
    songs = get_all_songs()
    if not songs:
        return None
    return random.choice(songs)


def get_random_song_by_category(category):
    songs = get_category_songs(category)
    if not songs:
        return None
    return random.choice(songs)


def increase_download(song_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE songs
        SET downloads = downloads + 1
        WHERE id = ?
        """,
        (int(song_id),)
    )

    conn.commit()
    conn.close()


def set_song_score(song_id, score):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE songs
        SET score = ?
        WHERE id = ?
        """,
        (float(score), int(song_id))
    )

    conn.commit()
    conn.close()


def add_song_score(song_id, delta):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE songs
        SET score = score + ?
        WHERE id = ?
        """,
        (float(delta), int(song_id))
    )

    conn.commit()
    conn.close()


def count_songs():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*)
        FROM songs
        WHERE is_active = 1
        """
    )

    total = cur.fetchone()[0]
    conn.close()
    return total


def count_downloads():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COALESCE(SUM(downloads), 0)
        FROM songs
        WHERE is_active = 1
        """
    )

    total = cur.fetchone()[0]
    conn.close()
    return int(total or 0)


def get_song_stats():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            COUNT(*),
            COALESCE(SUM(downloads), 0),
            COALESCE(AVG(score), 0)
        FROM songs
        WHERE is_active = 1
        """
    )

    row = cur.fetchone()
    conn.close()

    if not row:
        return {
            "songs": 0,
            "downloads": 0,
            "avg_score": 0.0,
        }

    return {
        "songs": int(row[0] or 0),
        "downloads": int(row[1] or 0),
        "avg_score": float(row[2] or 0.0),
    }
