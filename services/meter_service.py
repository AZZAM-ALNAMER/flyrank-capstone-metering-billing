from repositories.usage_repo import (
    find_by_idempotency_key,
    insert_usage_event,
    sum_usage_this_month,
    get_tenant,
    DuplicateIdempotencyKey,
)
from services.quota_service import check_quota


class TenantNotFound(Exception):
    pass


def record_usage(
    tenant_id: str,
    usage_type: str,
    quantity: int,
    idempotency_key: str,
    input_tokens: int = 0,
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
) -> tuple[dict, bool]:
    """
    Returns (event, was_duplicate).
    If the idempotency key was already used, returns the ORIGINAL event
    and was_duplicate=True — no new event is created, no quota is re-checked.
    """
    existing = find_by_idempotency_key(idempotency_key)
    if existing is not None:
        return existing, True

    tenant = get_tenant(tenant_id)
    if tenant is None:
        raise TenantNotFound(tenant_id)

    current_usage = sum_usage_this_month(tenant_id, usage_type)
    check_quota(tenant["plan"], usage_type, current_usage, quantity)

    try:
        event = insert_usage_event(
            tenant_id, usage_type, quantity, idempotency_key,
            input_tokens, cached_input_tokens, output_tokens, reasoning_tokens
        )
    except DuplicateIdempotencyKey:
        # Rare race: two requests with the same key arrived at nearly the
        # same instant and both passed the first check. The DB's UNIQUE
        # constraint caught it — fetch and return the one that won.
        event = find_by_idempotency_key(idempotency_key)

    return event, False