from django.urls import path

from .views import ConfirmPaymentView, CreatePaymentIntentView, StripeWebhookView

urlpatterns = [
    path("intent/", CreatePaymentIntentView.as_view(), name="payment-intent-create"),
    path("confirm/", ConfirmPaymentView.as_view(), name="payment-confirm"),
    path("webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
]
