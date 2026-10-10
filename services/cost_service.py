from config import (
    API_CALL_MICRO_USD,
    CACHED_INPUT_TOKEN_MICRO_USD_PER_MILLION,
    FRESH_INPUT_TOKEN_MICRO_USD_PER_MILLION,
    OUTPUT_TOKEN_MICRO_USD_PER_MILLION,
)

TOKENS_PER_MILLION = 1_000_000


def api_call_cost(count: int) -> int:
    return count * API_CALL_MICRO_USD


def token_cost(
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
) -> int:
    if cached_input_tokens > input_tokens:
        raise ValueError("cached_input_tokens cannot exceed input_tokens")

    fresh_input_tokens = input_tokens - cached_input_tokens
    billable_output_tokens = output_tokens + reasoning_tokens
    total_token_micro_usd = (
        fresh_input_tokens * FRESH_INPUT_TOKEN_MICRO_USD_PER_MILLION
        + cached_input_tokens * CACHED_INPUT_TOKEN_MICRO_USD_PER_MILLION
        + billable_output_tokens * OUTPUT_TOKEN_MICRO_USD_PER_MILLION
    )
    return total_token_micro_usd // TOKENS_PER_MILLION
