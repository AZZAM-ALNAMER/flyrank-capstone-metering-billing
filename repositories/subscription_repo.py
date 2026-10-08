from db import get_connection


def process_webhook_event(event: dict) -> str:
    """Apply a verified Stripe event and record it atomically.

    Returns "already processed" for a duplicate. Any processing failure rolls
    back the event marker so Stripe can retry the delivery.
    """
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT 1 FROM processed_webhook_events WHERE stripe_event_id = ?",
            (event["id"],),
        ).fetchone()
        if existing:
            conn.rollback()
            return "already processed"
        conn.execute(
            "INSERT INTO processed_webhook_events (stripe_event_id) VALUES (?)",
            (event["id"],),
        )

        event_type = event["type"]
        obj = event["data"]["object"]

        if event_type == "checkout.session.completed":
            tenant_id = obj.get("client_reference_id")
            if not tenant_id:
                raise ValueError("Checkout session is missing client_reference_id")
            if not obj.get("customer") or not obj.get("subscription"):
                raise ValueError("Checkout session is missing customer or subscription")

            conn.execute(
                """INSERT INTO subscriptions
                   (tenant_id, stripe_customer_id, stripe_subscription_id, status, updated_at)
                   VALUES (?, ?, ?, 'active', datetime('now'))
                   ON CONFLICT(tenant_id) DO UPDATE SET
                       stripe_customer_id = excluded.stripe_customer_id,
                       stripe_subscription_id = excluded.stripe_subscription_id,
                       status = excluded.status,
                       updated_at = datetime('now')""",
                (tenant_id, obj["customer"], obj["subscription"]),
            )
            updated = conn.execute(
                "UPDATE tenants SET plan = 'pro' WHERE id = ?", (tenant_id,)
            )
            if updated.rowcount != 1:
                raise ValueError(f"No tenant found for checkout session: {tenant_id}")

        elif event_type == "customer.subscription.deleted":
            conn.execute(
                "UPDATE subscriptions SET status = ?, updated_at = datetime('now') WHERE stripe_subscription_id = ?",
                (obj.get("status", "canceled"), obj["id"]),
            )
            conn.execute(
                "UPDATE tenants SET plan = 'free' WHERE id = (SELECT tenant_id FROM subscriptions WHERE stripe_subscription_id = ?)",
                (obj["id"],),
            )

        elif event_type == "customer.subscription.updated":
            conn.execute(
                """UPDATE subscriptions SET stripe_customer_id = ?, status = ?, updated_at = datetime('now')
                   WHERE stripe_subscription_id = ?""",
                (obj["customer"], obj["status"], obj["id"]),
            )

        conn.commit()
        return "processed"
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
