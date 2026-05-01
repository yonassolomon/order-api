import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer

from .serializers import (
    PaymentConfirmSerializer,
    PaymentIntentCreateSerializer,
    PaymentIntentResponseSerializer,
)
from .services import create_payment_intent, fulfill_order_if_paid


class CreatePaymentIntentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=PaymentIntentCreateSerializer,
        responses={200: PaymentIntentResponseSerializer},
    )
    def post(self, request):
        if request.user.role != User.Role.CUSTOMER:
            return Response(
                {"detail": "Only customers can pay for orders."},
                status=status.HTTP_403_FORBIDDEN,
            )
        ser = PaymentIntentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        order_id = ser.validated_data["order_id"]
        try:
            order = Order.objects.get(pk=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            intent = create_payment_intent(order, request.user)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(
            {"client_secret": intent.client_secret, "payment_intent_id": intent.id},
            status=status.HTTP_200_OK,
        )


class ConfirmPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=PaymentConfirmSerializer,
        responses={200: OrderSerializer},
    )
    def post(self, request):
        if request.user.role != User.Role.CUSTOMER:
            return Response(
                {"detail": "Only customers can confirm payments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        ser = PaymentConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payment_intent_id = ser.validated_data["payment_intent_id"]
        if not settings.STRIPE_SECRET_KEY:
            return Response(
                {"detail": "Stripe is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        except stripe.error.StripeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        meta = intent.metadata or {}
        order_id = meta.get("order_id")
        if not order_id:
            return Response(
                {"detail": "Missing order metadata on PaymentIntent."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            order = Order.objects.get(pk=int(order_id), user=request.user)
        except (ValueError, Order.DoesNotExist):
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            order = fulfill_order_if_paid(order.id, intent.id, intent.status)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        if not settings.STRIPE_WEBHOOK_SECRET:
            return Response({"detail": "Webhook not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if event["type"] == "payment_intent.succeeded":
            intent = event["data"]["object"]
            meta = intent.get("metadata") or {}
            order_id = meta.get("order_id")
            if order_id:
                try:
                    fulfill_order_if_paid(int(order_id), intent["id"], intent["status"])
                except (ValueError, Order.DoesNotExist):
                    pass
        return Response(status=status.HTTP_200_OK)
