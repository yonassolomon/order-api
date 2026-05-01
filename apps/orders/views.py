from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import IsAdminRole

from .models import Order
from .serializers import OrderSerializer
from .services import create_order_from_cart


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Order.objects.prefetch_related("items").all()
        if self.request.user.role == User.Role.ADMIN:
            return qs
        return qs.filter(user=self.request.user)

    @extend_schema(
        request=None,
        responses={201: OrderSerializer},
        summary="Create order from current cart (customer)",
    )
    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def checkout(self, request):
        if request.user.role != User.Role.CUSTOMER:
            return Response(
                {"detail": "Only customers can checkout."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            order = create_order_from_cart(request.user)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=None,
        responses={200: OrderSerializer},
        summary="Mark order as shipped (admin)",
    )
    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAuthenticated, IsAdminRole],
        url_path="ship",
    )
    def ship(self, request, pk=None):
        order = self.get_object()
        if order.status != Order.Status.PAID:
            return Response(
                {"detail": "Order must be paid before shipping."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order.status = Order.Status.SHIPPED
        order.save(update_fields=["status", "updated_at"])
        return Response(OrderSerializer(order).data)
