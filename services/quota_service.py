PLAN_QUOTAS = {
    "free": {"api_call": 1_000, "ai_tokens": 100_000},
    "pro": {"api_call": 50_000, "ai_tokens": 5_000_000},
}


class QuotaExceeded(Exception):
    def __init__(self, message: str, status_code: int):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def check_quota(plan: str, usage_type: str, current_usage: int, requested_quantity: int):
    if usage_type not in PLAN_QUOTAS.get(plan, {}):
        raise QuotaExceeded(
            f"Plan '{plan}' does not include usage type '{usage_type}'",
            status_code=402
        )

    limit = PLAN_QUOTAS[plan][usage_type]

    if current_usage + requested_quantity > limit:
        raise QuotaExceeded(
            f"Quota exceeded: {current_usage}/{limit} {usage_type} used this month, "
            f"request of {requested_quantity} would exceed the limit",
            status_code=429
        )