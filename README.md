# Usage Metering & Billing Engine

A backend service that answers three questions: how much has this tenant
used, what does it cost, and have they hit their limit? It meters usage
idempotently, enforces plan quotas, prices AI tokens with real-world rules,
and syncs plans with Stripe (test mode) through verified webhooks.

## Architecture

```
Client -> POST /generate -> MeterService.record(tenant, type, qty, key)
                              | key seen before? -> return original event
                              | QuotaService.check -> 429 / 402 if over
                              | insert usage_event (UNIQUE idempotency_key)
Client -> GET /usage     -> rollup(usage_events) -> used / limit / cost

Stripe Checkout -> subscription created
Stripe --signed webhook--> /webhooks/stripe
                              | verify signature (forged -> 400)
                              | dedupe by event id (replay -> ignored)
                              | update tenant plan / status
```

Layers: `main.py` (HTTP) -> `services/` (logic) -> `repositories/` (SQL).

## Run it

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then fill in your Stripe TEST keys
python seed.py              # creates tenant-free-1 and tenant-pro-1
uvicorn main:app --reload
```

For Stripe webhooks, in a second terminal:

```bash
stripe listen --events checkout.session.completed,customer.subscription.updated,customer.subscription.deleted --forward-to localhost:8000/webhooks/stripe
```

Copy the `whsec_...` it prints into `.env` and restart the API.
Docs: http://localhost:8000/docs

## Plans

| Plan | API calls / month | AI tokens / month |
|---|---|---|
| Free | 1,000 | 100,000 |
| Pro | 50,000 | 5,000,000 |

## Boundary rule

A request is allowed if `current_usage + requested <= limit`. At 999/1000 a
request of 1 succeeds; at 1000/1000 any request returns 429.

## Pricing (integer micro-USD, 1 = $0.000001)

| Item | Price |
|---|---|
| API call | $0.002 |
| Fresh input tokens | $1.00 / 1M |
| Cached input tokens | $0.25 / 1M |
| Output tokens | $4.00 / 1M |
| Reasoning tokens | billed as output |

## Limitations

- SQLite, with schema created at startup (no migration tool).
- No authentication: tenants are isolated by `tenant_id` filtering, but any
  caller can pass any tenant id.
- The 402 path exists for plans that don't include a usage type, but the two
  current plans both include both types, so it isn't reachable today.
- The quota check and insert are not one atomic step, so two concurrent
  requests with different keys could both pass at the boundary.
- No background job, invoicing, proration, or overage billing.