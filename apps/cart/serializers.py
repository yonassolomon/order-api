from rest_framework import serializers

from apps.products.models import Product
from apps.products.serializers import ProductSerializer

from .models import CartItem


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source="product",
        write_only=True,
    )
    quantity = serializers.IntegerField(required=False, default=1, min_value=1)

    class Meta:
        model = CartItem
        fields = ("id", "product", "product_id", "quantity")
        read_only_fields = ("id", "product")


class CartSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
