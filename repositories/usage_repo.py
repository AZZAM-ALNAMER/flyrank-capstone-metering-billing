import sqlite3
from db import get_connection


class DuplicateIdempotencyKey(Exception):
    """Raised when an idempotency key was already used — the caller
    should fetch and return the original event, not treat this as an error."""
    pass


def find_by_idempotency_key(idempotency_key: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM usage_events WHERE idempotency_key = ?",
        (idempotency_key,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def insert_usage_event(
    tenant_id: str,
    usage_type: str,
    quantity: int,
    idempotency_key: str,
    input_tokens: int = 0,
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
) -> dict:
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO usage_events
               (tenant_id, usage_type, quantity, idempotency_key,
                input_tokens, cached_input_tokens, output_tokens, reasoning_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (tenant_id, usage_type, quantity, idempotency_key,
             input_tokens, cached_input_tokens, output_tokens, reasoning_tokens)
        )
        conn.commit()
        new_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise DuplicateIdempotencyKey(idempotency_key)

    row = conn.execute("SELECT * FROM usage_events WHERE id = ?", (new_id,)).fetchone()
    conn.close()
    return dict(row)


def sum_usage_this_month(tenant_id: str, usage_type: str) -> int:
    conn = get_connection()
    row = conn.execute(
        """SELECT COALESCE(SUM(quantity), 0) as total
           FROM usage_events
           WHERE tenant_id = ? AND usage_type = ?
           AND created_at >= date('now', 'start of month')""",
        (tenant_id, usage_type)
    ).fetchone()
    conn.close()
    return row["total"]


def get_tenant(tenant_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    conn.close()
    return dict(row) if row else None