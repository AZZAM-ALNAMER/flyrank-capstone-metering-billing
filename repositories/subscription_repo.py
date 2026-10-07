from db import get_connection


def upsert_subscription(tenant_id: str, stripe_customer_id: str, stripe_subscription_id: str, status: str):
    conn = get_connection()
    conn.execute("""
        INSERT INTO subscriptions (tenant_id, stripe_customer_id, stripe_subscription_id, status, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(tenant_id) DO UPDATE SET
            stripe_customer_id = excluded.stripe_customer_id,
            stripe_subscription_id = excluded.stripe_subscription_id,
            status = excluded.status,
            updated_at = datetime('now')
    """, (tenant_id, stripe_customer_id, stripe_subscription_id, status))
    conn.commit()
    conn.close()


def update_tenant_plan(tenant_id: str, plan: str):
    conn = get_connection()
    conn.execute("UPDATE tenants SET plan = ? WHERE id = ?", (plan, tenant_id))
    conn.commit()
    conn.close()


def mark_event_processed(event_id: str) -> bool:
    """Returns True if this is a new event (not seen before), False if it's a duplicate."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO processed_webhook_events (stripe_event_id) VALUES (?)",
            (event_id,)
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False