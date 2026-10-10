import os
import stripe
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Literal, Optional
from dotenv import load_dotenv

from db import init_db
from services.meter_service import record_usage, TenantNotFound
from services.quota_service import QuotaExceeded, PLAN_QUOTAS
from services.stripe_service import create_checkout_session
from repositories.usage_repo import sum_usage_this_month, sum_token_columns_this_month, get_tenant
from services.cost_service import api_call_cost, token_cost
from repositories.subscription_repo import process_webhook_event

load_dotenv()

app = FastAPI(title="Usage Metering & Billing Engine")

init_db()

STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]


# ---------- Schemas ----------

class TokenUsage(BaseModel):
    input: int = 0
    cached_input: int = 0
    output: int = 0
    reasoning: int = 0


class GenerateRequest(BaseModel):
    tenant_id: str
    idempotency_key: str
    usage_type: Literal["api_call", "ai_tokens"]
    quantity: Optional[int] = None
    tokens: Optional[TokenUsage] = None


# ---------- Health ----------

@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Metering ----------

@app.post("/generate")
def generate(body: GenerateRequest):
    if body.usage_type == "api_call":
        quantity = body.quantity or 1
        token_fields = {}
    else:
        if body.tokens is None:
            raise HTTPException(status_code=400, detail="tokens required for ai_tokens usage_type")
        if body.tokens.cached_input > body.tokens.input:
            raise HTTPException(
                status_code=400,
                detail="cached_input cannot exceed input",
            )
        quantity = body.tokens.input + body.tokens.output + body.tokens.reasoning
        token_fields = {
            "input_tokens": body.tokens.input,
            "cached_input_tokens": body.tokens.cached_input,
            "output_tokens": body.tokens.output,
            "reasoning_tokens": body.tokens.reasoning,
        }

    try:
        event, was_duplicate = record_usage(
            tenant_id=body.tenant_id,
            usage_type=body.usage_type,
            quantity=quantity,
            idempotency_key=body.idempotency_key,
            **token_fields
        )
    except TenantNotFound:
        raise HTTPException(status_code=404, detail="Tenant not found")
    except QuotaExceeded as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return {"event": event, "duplicate": was_duplicate}


@app.get("/usage")
def usage(tenant_id: str):
    tenant = get_tenant(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    quotas = PLAN_QUOTAS.get(tenant["plan"], {})

    result = {"tenant_id": tenant_id, "plan": tenant["plan"], "usage": {}}
    for usage_type, limit in quotas.items():
        used = sum_usage_this_month(tenant_id, usage_type)
        result["usage"][usage_type] = {"used": used, "limit": limit}

    api_call_micro_usd = api_call_cost(sum_usage_this_month(tenant_id, "api_call"))
    token_totals = sum_token_columns_this_month(tenant_id)
    ai_tokens_micro_usd = token_cost(
        token_totals["input_tokens"],
        token_totals["cached_input_tokens"],
        token_totals["output_tokens"],
        token_totals["reasoning_tokens"],
    )
    total_micro_usd = api_call_micro_usd + ai_tokens_micro_usd
    total_usd = f"{total_micro_usd // 1_000_000}.{total_micro_usd % 1_000_000:06d}"
    result["cost"] = {
        "api_call_micro_usd": api_call_micro_usd,
        "ai_tokens_micro_usd": ai_tokens_micro_usd,
        "total_micro_usd": total_micro_usd,
        "total_usd": total_usd,
    }

    return result


# ---------- Stripe: Checkout ----------

@app.post("/checkout")
def checkout(tenant_id: str):
    tenant = get_tenant(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    url = create_checkout_session(tenant_id)
    return {"checkout_url": url}


# ---------- Stripe: Webhooks ----------

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    # Stripe returns StripeObject instances; convert nested data to dicts before
    # repository code accesses fields with normal dictionary methods such as get().
    event = event.to_dict()
    result = process_webhook_event(event)
    return {"status": result}




@app.get("/checkout-success")
def checkout_success():
    return {"message": "Payment received. Your plan updates in a few seconds. Check GET /usage."}


@app.get("/checkout-cancel")
def checkout_cancel():
    return {"message": "Checkout cancelled. No charge was made."}
