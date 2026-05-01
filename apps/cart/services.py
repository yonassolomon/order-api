from django.db import transaction

from .models import Cart


def get_or_create_cart(user):
    with transaction.atomic():
        cart, _ = Cart.objects.select_for_update().get_or_create(user=user)
    return cart
