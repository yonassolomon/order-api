from decimal import Decimal

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User

from .models import CartItem
from .serializers import CartItemSerializer, CartSerializer
from .services import get_or_create_cart


def cart_total(cart):
    total = Decimal("0.00")
    for item in cart.items.select_related("product"):
        total += item.product.price * item.quantity
    return total


class CartDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: CartSerializer})
    def get(self, request):
        if request.user.role != User.Role.CUSTOMER:
            return Response(
                {"detail": "Only customers have a cart."},
                status=status.HTTP_403_FORBIDDEN,
            )
        cart = get_or_create_cart(request.user)
        data = {
            "id": cart.id,
            "items": CartItemSerializer(cart.items.all(), many=True).data,
            "total": cart_total(cart),
        }
        return Response(data)


class CartItemAddView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=CartItemSerializer, responses={201: CartItemSerializer})
    def post(self, request):
        if request.user.role != User.Role.CUSTOMER:
            return Response(
                {"detail": "Only customers can modify the cart."},
                status=status.HTTP_403_FORBIDDEN,
            )
        cart = get_or_create_cart(request.user)
        ser = CartItemSerializer(data=request.data, context={"cart": cart})
        ser.is_valid(raise_exception=True)
        product = ser.validated_data["product"]
        quantity = ser.validated_data.get("quantity", 1)
        item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": quantity})
        if not created:
            item.quantity += quantity
            item.save(update_fields=["quantity"])
        return Response(CartItemSerializer(item).data, status=status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_item(self, request, pk):
        cart = get_or_create_cart(request.user)
        try:
            return cart.items.get(pk=pk)
        except CartItem.DoesNotExist:
            return None

    @extend_schema(request=CartItemSerializer, responses={200: CartItemSerializer})
    def patch(self, request, pk):
        if request.user.role != User.Role.CUSTOMER:
            return Response(
                {"detail": "Only customers can modify the cart."},
                status=status.HTTP_403_FORBIDDEN,
            )
        item = self.get_item(request, pk)
        if not item:
            return Response(status=status.HTTP_404_NOT_FOUND)
        quantity = request.data.get("quantity")
        if quantity is None:
            return Response({"quantity": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response({"quantity": ["Must be a positive integer."]}, status=status.HTTP_400_BAD_REQUEST)
        if quantity < 1:
            return Response({"quantity": ["Must be at least 1."]}, status=status.HTTP_400_BAD_REQUEST)
        item.quantity = quantity
        item.save(update_fields=["quantity"])
        return Response(CartItemSerializer(item).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        if request.user.role != User.Role.CUSTOMER:
            return Response(
                {"detail": "Only customers can modify the cart."},
                status=status.HTTP_403_FORBIDDEN,
            )
        item = self.get_item(request, pk)
        if not item:
            return Response(status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
