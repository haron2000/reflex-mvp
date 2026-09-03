from django.contrib import admin
from .models import UserProfile, DeliveryRequest, StatusEvent


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "shop_name", "phone_number", "is_active_rider")
    list_filter = ("role", "is_active_rider")


class StatusEventInline(admin.TabularInline):
    model = StatusEvent
    extra = 0
    readonly_fields = ("status", "changed_by", "note", "timestamp")
    can_delete = False


@admin.register(DeliveryRequest)
class DeliveryRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_name", "status", "assigned_rider", "retailer", "created_at")
    list_filter = ("status",)
    search_fields = ("customer_name", "customer_phone", "item_description")
    readonly_fields = ("qr_token", "version", "created_at", "updated_at")
    inlines = [StatusEventInline]


@admin.register(StatusEvent)
class StatusEventAdmin(admin.ModelAdmin):
    list_display = ("request", "status", "changed_by", "timestamp")
    readonly_fields = ("request", "status", "changed_by", "note", "timestamp")
