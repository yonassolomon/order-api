from decimal import Decimal

from django.db import transaction

from apps.cart.models import CartItem
from apps.cart.services import get_or_create_cart

from .models import Order, OrderItem


def compute_cart_total(cart):
    total = Decimal("0.00")
    items = list(cart.items.select_related("product"))
    for line in items:
        total += line.product.price * line.quantity
    return total, items


@transaction.atomic
def create_order_from_cart(user):
    cart = get_or_create_cart(user)
    total, lines = compute_cart_total(cart)
    if not lines:
        raise ValueError("Cart is empty.")

    for line in lines:
        if line.product.stock < line.quantity:
            raise ValueError(
                f"Insufficient stock for '{line.product.name}' (available {line.product.stock}).",
            )

    order = Order.objects.create(user=user, total_amount=total, status=Order.Status.PENDING)
    for line in lines:
        OrderItem.objects.create(
            order=order,
            product=line.product,
            product_name=line.product.name,
            unit_price=line.product.price,
            quantity=line.quantity,
        )
    CartItem.objects.filter(cart=cart).delete()
    return order
