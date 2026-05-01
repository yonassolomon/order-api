from rest_framework import serializers


class PaymentIntentCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()


class PaymentIntentResponseSerializer(serializers.Serializer):
    client_secret = serializers.CharField()
    payment_intent_id = serializers.CharField()


class PaymentConfirmSerializer(serializers.Serializer):
    payment_intent_id = serializers.CharField()
