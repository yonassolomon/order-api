from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.cart.models import Cart

from .models import User


@receiver(post_save, sender=User)
def create_cart_for_customer(sender, instance, created, **kwargs):
    if created and instance.role == User.Role.CUSTOMER:
        Cart.objects.get_or_create(user=instance)
