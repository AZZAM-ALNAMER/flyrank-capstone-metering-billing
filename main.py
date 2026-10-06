from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Literal, Optional

from db import init_db
from services.meter_service import record_usage, TenantNotFound
from services.quota_service import QuotaExceeded
from repositories.usage_repo import sum_usage_this_month, get_tenant

app = FastAPI(title="Usage Metering & Billing Engine")

init_db()


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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate")
def generate(body: GenerateRequest):
    if body.usage_type == "api_call":
        quantity = body.quantity or 1
        token_fields = {}
    else:
        if body.tokens is None:
            raise HTTPException(status_code=400, detail="tokens required for ai_tokens usage_type")
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

    from services.quota_service import PLAN_QUOTAS
    quotas = PLAN_QUOTAS.get(tenant["plan"], {})

    result = {"tenant_id": tenant_id, "plan": tenant["plan"], "usage": {}}
    for usage_type, limit in quotas.items():
        used = sum_usage_this_month(tenant_id, usage_type)
        result["usage"][usage_type] = {"used": used, "limit": limit}

    return result