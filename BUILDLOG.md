# Build log (AI usage)

## Where AI helped
- Drafted the schema, idempotent metering, quota logic, Stripe handler, and
  cost calculator.
- A coding agent diagnosed why the webhook wasn't upgrading the tenant and
  implemented the Phase 4 cost calculation.

## Where AI was wrong, and what I changed
- Told me to use the product ID for `STRIPE_PRO_PRICE_ID`. Stripe needs the
  `price_` ID, so checkout returned a 500 until I fixed it.
- Used `stripe.error.SignatureVerificationError`, which was removed in the
  Stripe library version I installed. Changed to `stripe.SignatureVerificationError`.
- Gave a `stripe listen` command without `--events`, which the current CLI requires.
- Suggested `stripe trigger checkout.session.completed` for the duplicate
  test, but triggered events have no `client_reference_id`, so they can't
  upgrade a real tenant. I replayed a real event instead.


## What I verified myself
- Same idempotency key twice leaves usage and cost unchanged.
- Cost for the worked example matches 3100 micro-USD by hand.
- A forged webhook returns 400.