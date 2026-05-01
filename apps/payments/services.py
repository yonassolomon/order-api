from decimal import Decimal

import stripe
from django.conf import settings
from django.db import transaction

from apps.accounts.models import User
from apps.orders.models import Order

stripe.api_key = settings.STRIPE_SECRET_KEY


def _amount_cents(total: Decimal) -> int:
    return int((total * 100).quantize(Decimal("1")))


def create_payment_intent(order: Order, user: User):
    if order.user_id != user.id:
        raise PermissionError("Order does not belong to this user.")
    if order.status != Order.Status.PENDING:
        raise ValueError("Only pending orders can be paid.")
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError("Stripe is not configured (missing STRIPE_SECRET_KEY).")

    intent = stripe.PaymentIntent.create(
        amount=_amount_cents(order.total_amount),
        currency="usd",
        metadata={"order_id": str(order.id), "user_id": str(user.id)},
        automatic_payment_methods={"enabled": True},
    )
    order.stripe_payment_intent_id = intent.id
    order.save(update_fields=["stripe_payment_intent_id", "updated_at"])
    return intent


@transaction.atomic
def fulfill_order_if_paid(order_id: int, payment_intent_id: str, stripe_status: str) -> Order:
    order = Order.objects.select_for_update().get(pk=order_id)
    if stripe_status != "succeeded":
        raise ValueError("Payment has not succeeded.")

    if order.stripe_payment_intent_id and order.stripe_payment_intent_id != payment_intent_id:
        raise ValueError("PaymentIntent does not match this order.")

    if order.status == Order.Status.PAID:
        return order

    if order.status != Order.Status.PENDING:
        raise ValueError("Order cannot be paid in its current state.")

    for item in order.items.select_related("product"):
        if item.product_id is None:
            raise ValueError("Order line missing product reference.")
        product = item.product
        if product.stock < item.quantity:
            raise ValueError(f"Insufficient stock for '{product.name}'.")
        product.stock -= item.quantity
        product.save(update_fields=["stock", "updated_at"])

    order.status = Order.Status.PAID
    if not order.stripe_payment_intent_id:
        order.stripe_payment_intent_id = payment_intent_id
    order.save(update_fields=["status", "stripe_payment_intent_id", "updated_at"])
    return order
