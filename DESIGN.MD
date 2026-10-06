# Design — Usage Metering & Billing Engine

## Problem
Every SaaS needs to answer: how much has this tenant used, what does it
cost, and have they hit their limit? This service meters usage, enforces
quotas, calculates cost, and keeps plan state in sync with Stripe.

## Non-goal
No invoicing, proration, or overage billing in the core build — those are
explicit stretch goals, not required here.

## Data model

**tenants**
- id (PK)
- name
- plan (enum: free, pro)
- created_at

**usage_events**
- id (PK)
- tenant_id (FK)
- type (enum: api_call, ai_tokens)
- quantity (integer)
- idempotency_key (unique, indexed)
- created_at

**subscriptions**
- id (PK)
- tenant_id (FK)
- stripe_customer_id
- stripe_subscription_id
- status (enum: active, canceled, past_due)
- updated_at

**processed_webhook_events**
- stripe_event_id (PK) — used to detect and ignore duplicate webhook deliveries

## Plans & quotas

| Plan | API calls / month | AI tokens / month |
|---|---|---|
| Free | 1,000 | 100,000 |
| Pro | 50,000 | 5,000,000 |

## Metering API contract

`POST /generate`
```json
{
  "tenant_id": "...",
  "idempotency_key": "...",
  "usage_type": "api_call" | "ai_tokens",
  "quantity": 1
}
```

## Idempotency strategy

`idempotency_key` is a unique column on `usage_events`. Before inserting,
check if a row with that key already exists:
- **Exists** → return the original result, insert nothing new
- **Doesn't exist** → check quota, then insert

This makes the write a single atomic check-then-insert against a unique
constraint, so a duplicate retry can never create a second row — the
database itself enforces uniqueness, not just application logic.

## Quota enforcement

Before inserting a usage event:
1. Sum this tenant's usage for the current calendar month, for that usage type
2. If `current_usage + requested_quantity > plan_limit` → reject
3. Reject as `429` if under a paid plan but over its limit (temporary, usage-based)
4. Reject as `402` if the tenant's plan itself doesn't cover this usage type at all

## Cost calculation

Store pricing as pinned constants (cents per unit). AI token cost: