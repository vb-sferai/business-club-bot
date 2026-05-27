"""
Слой работы с базой данных (PostgreSQL через psycopg 3).

Таблицы:
  - users     — все пользователи бота, включая статус заявки;
  - questions — вопросы, которые задают пользователи, и ответы админов;
  - kv        — ключ/значение для редактируемых текстов сообщений.
"""

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from config import DATABASE_URL


@contextmanager
def get_conn() -> Iterator[psycopg.Connection]:
    """Контекстный менеджер: возвращает соединение и автоматически коммитит."""
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Создаёт таблицы при первом запуске."""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id        BIGINT PRIMARY KEY,
                tg_username    TEXT,
                full_name      TEXT,
                phone          TEXT,
                club_username  TEXT,
                comment        TEXT,
                status         TEXT DEFAULT 'started',
                applied_at     TIMESTAMP,
                updated_at     TIMESTAMP,
                is_banned      BOOLEAN DEFAULT FALSE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id           BIGSERIAL PRIMARY KEY,
                user_id      BIGINT NOT NULL,
                text         TEXT NOT NULL,
                status       TEXT DEFAULT 'new',
                answer_text  TEXT,
                created_at   TIMESTAMP NOT NULL,
                answered_at  TIMESTAMP,
                answered_by  BIGINT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_questions_status "
            "ON questions(status, created_at DESC)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kv (
                key   TEXT PRIMARY KEY,
                value JSONB NOT NULL
            )
            """
        )


# ---------- Пользователи ----------

def ensure_user(user_id: int, tg_username: Optional[str]) -> None:
    """Создаёт запись при первом контакте, иначе обновляет ник Telegram."""
    now = datetime.utcnow()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id FROM users WHERE user_id = %s", (user_id,)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO users (user_id, tg_username, status, updated_at) "
                "VALUES (%s, %s, 'started', %s)",
                (user_id, tg_username, now),
            )
        else:
            conn.execute(
                "UPDATE users SET tg_username = %s, updated_at = %s WHERE user_id = %s",
                (tg_username, now, user_id),
            )


def get_user(user_id: int) -> Optional[dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE user_id = %s", (user_id,)
        ).fetchone()
        return dict(row) if row else None


def find_user_by_username(username: str) -> Optional[dict[str, Any]]:
    """Ищет пользователя по @username (без собачки)."""
    username = username.lstrip("@")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE LOWER(tg_username) = LOWER(%s)", (username,)
        ).fetchone()
        return dict(row) if row else None


def save_application(
    user_id: int,
    full_name: str,
    phone: str,
    club_username: str,
    comment: str,
) -> None:
    """Сохраняет заполненную анкету, переводит статус в 'pending'."""
    now = datetime.utcnow()
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE users
            SET full_name = %s, phone = %s, club_username = %s, comment = %s,
                status = 'pending', applied_at = %s, updated_at = %s
            WHERE user_id = %s
            """,
            (full_name, phone, club_username, comment, now, now, user_id),
        )


def list_applications(status: Optional[str] = None) -> list[dict[str, Any]]:
    """Возвращает заявки с указанным статусом, отсортированные по дате (новые сверху)."""
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM users WHERE status = %s "
                "ORDER BY applied_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM users "
                "WHERE status IN ('pending','approved','rejected') "
                "ORDER BY applied_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def set_status(user_id: int, status: str) -> None:
    now = datetime.utcnow()
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET status = %s, updated_at = %s WHERE user_id = %s",
            (status, now, user_id),
        )


def all_user_ids() -> list[int]:
    """ID всех пользователей бота, доступных для рассылки (не забаненных)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id FROM users WHERE is_banned = FALSE"
        ).fetchall()
        return [r["user_id"] for r in rows]


# ---------- Вопросы ----------

def save_question(user_id: int, text: str) -> int:
    """Сохраняет вопрос пользователя. Возвращает id записи."""
    now = datetime.utcnow()
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO questions (user_id, text, status, created_at) "
            "VALUES (%s, %s, 'new', %s) RETURNING id",
            (user_id, text, now),
        ).fetchone()
        return row["id"]


def get_question(question_id: int) -> Optional[dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM questions WHERE id = %s", (question_id,)
        ).fetchone()
        return dict(row) if row else None


def list_questions(status: Optional[str] = None) -> list[dict[str, Any]]:
    """Возвращает вопросы (опционально с фильтром по статусу), новые сверху."""
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM questions WHERE status = %s "
                "ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM questions ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def count_new_questions() -> int:
    """Сколько вопросов ждут ответа (для бейджа в меню админа)."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS c FROM questions WHERE status='new'"
        ).fetchone()["c"]


def mark_question_answered(
    question_id: int, admin_id: int, answer_text: str
) -> None:
    """Сохраняет ответ админа на вопрос и переводит его в 'answered'."""
    now = datetime.utcnow()
    with get_conn() as conn:
        conn.execute(
            "UPDATE questions SET status='answered', answered_at=%s, "
            "answered_by=%s, answer_text=%s WHERE id=%s",
            (now, admin_id, answer_text, question_id),
        )


def mark_question_closed(question_id: int) -> None:
    """Закрыть вопрос без ответа."""
    now = datetime.utcnow()
    with get_conn() as conn:
        conn.execute(
            "UPDATE questions SET status='closed', answered_at=%s WHERE id=%s",
            (now, question_id),
        )


# ---------- Статистика ----------

def stats() -> dict[str, int]:
    """Сводная статистика по пользователям и вопросам."""
    with get_conn() as conn:

        def _count_users(where: str = "") -> int:
            return conn.execute(
                f"SELECT COUNT(*) AS c FROM users {where}"
            ).fetchone()["c"]

        def _count_questions(where: str = "") -> int:
            return conn.execute(
                f"SELECT COUNT(*) AS c FROM questions {where}"
            ).fetchone()["c"]

        return {
            "total": _count_users(),
            "started": _count_users("WHERE status='started'"),
            "pending": _count_users("WHERE status='pending'"),
            "approved": _count_users("WHERE status='approved'"),
            "rejected": _count_users("WHERE status='rejected'"),
            "questions_total": _count_questions(),
            "questions_new": _count_questions("WHERE status='new'"),
            "questions_answered": _count_questions("WHERE status='answered'"),
            "questions_closed": _count_questions("WHERE status='closed'"),
        }


# ---------- Key/Value (тексты сообщений) ----------

def kv_get(key: str) -> Optional[dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM kv WHERE key = %s", (key,)
        ).fetchone()
        return row["value"] if row else None


def kv_set(key: str, value: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO kv (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (key, Jsonb(value)),
        )
