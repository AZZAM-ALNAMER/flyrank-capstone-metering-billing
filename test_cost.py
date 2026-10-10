from services.cost_service import api_call_cost, token_cost


assert token_cost(1000, 400, 500, 100) == 3100
assert token_cost(1000, 1000, 0, 0) < token_cost(1000, 0, 0, 0)
assert token_cost(0, 0, 5, 5) == token_cost(0, 0, 10, 0)
assert api_call_cost(3) == 6000

try:
    token_cost(5, 6, 0, 0)
except ValueError:
    pass
else:
    raise AssertionError("cached_input_tokens > input_tokens must raise ValueError")

assert token_cost(0, 0, 0, 0) == 0
assert api_call_cost(0) == 0

print("All cost tests passed")
