from django.contrib.auth.models import User
from rest_framework import serializers

from .models import DeliveryRequest, StatusEvent


class StatusEventSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.username", read_only=True, default="")

    class Meta:
        model = StatusEvent
        fields = ["id", "status", "changed_by_name", "note", "timestamp"]


class RiderSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


class DeliveryRequestSerializer(serializers.ModelSerializer):
    history = StatusEventSerializer(many=True, read_only=True)
    assigned_rider_name = serializers.CharField(source="assigned_rider.username", read_only=True, default="")
    retailer_name = serializers.CharField(source="retailer.username", read_only=True)

    class Meta:
        model = DeliveryRequest
        fields = [
            "id",
            "customer_name",
            "customer_phone",
            "customer_address",
            "item_description",
            "status",
            "assigned_rider",
            "assigned_rider_name",
            "retailer_name",
            "qr_token",
            "version",
            "created_at",
            "updated_at",
            "history",
        ]
        read_only_fields = ["status", "qr_token", "version", "created_at", "updated_at"]


class CreateDeliveryRequestSerializer(serializers.ModelSerializer):
    """Retailer-facing create form -- only the fields a retailer should set."""

    class Meta:
        model = DeliveryRequest
        fields = ["customer_name", "customer_phone", "customer_address", "item_description"]

    def validate_customer_phone(self, value):
        digits = value.replace(" ", "").replace("-", "")
        if len(digits) < 9:
            raise serializers.ValidationError("Enter a valid phone number.")
        return value


class AssignSerializer(serializers.Serializer):
    rider_id = serializers.IntegerField()
    version = serializers.IntegerField()


class ScanSerializer(serializers.Serializer):
    qr_token = serializers.UUIDField()
    version = serializers.IntegerField()
