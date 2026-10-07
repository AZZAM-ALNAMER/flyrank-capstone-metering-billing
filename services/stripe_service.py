import os
import stripe
from dotenv import load_dotenv

load_dotenv()

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
PRO_PRICE_ID = os.environ["STRIPE_PRO_PRICE_ID"]


def create_checkout_session(tenant_id: str) -> str:
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": PRO_PRICE_ID, "quantity": 1}],
        success_url="http://localhost:8000/checkout-success",
        cancel_url="http://localhost:8000/checkout-cancel",
        client_reference_id=tenant_id,  # how we map the session back to our tenant
    )
    return session.url