import uuid

from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """Extends Django's built-in User with a Reflex role and shop info.

    We use Django's own auth (User) rather than rolling custom auth, so
    password reset, sessions, and the admin all work for free. Role decides
    which dashboard a user lands on and which API actions they're allowed.
    """

    class Role(models.TextChoices):
        RETAILER = "RETAILER", "Retailer staff"
        DISPATCHER = "DISPATCHER", "Dispatcher"
        RIDER = "RIDER", "Rider"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=Role.choices)
    shop_name = models.CharField(max_length=120, blank=True, help_text="Only used for retailer staff")
    phone_number = models.CharField(max_length=20, blank=True)
    is_active_rider = models.BooleanField(default=True, help_text="Riders can be paused without deleting the account")

    def __str__(self):
        return f"{self.user.get_username()} ({self.role})"


class DeliveryRequest(models.Model):
    """The single source of truth for one delivery, start to finish.

    Status only ever moves forward (see ALLOWED_TRANSITIONS below) and every
    change is mirrored into StatusEvent, so the record is append-only and
    auditable -- that's the whole point versus a WhatsApp thread.
    """

    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        ASSIGNED = "ASSIGNED", "Assigned"
        PICKED_UP = "PICKED_UP", "Picked up"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    # Forward-only transitions. Enforced in save-time helper methods below,
    # not just in the frontend, so a stray API call can't skip steps.
    ALLOWED_TRANSITIONS = {
        Status.REQUESTED: {Status.ASSIGNED, Status.CANCELLED},
        Status.ASSIGNED: {Status.PICKED_UP, Status.CANCELLED},
        Status.PICKED_UP: {Status.DELIVERED, Status.CANCELLED},
        Status.DELIVERED: set(),
        Status.CANCELLED: set(),
    }

    retailer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requests_created"
    )
    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=20)
    customer_address = models.TextField()
    item_description = models.TextField()

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    assigned_rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requests_assigned",
    )

    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Optimistic locking: the client sends back the version it last read.
    # If it doesn't match, someone else changed the record first -> 409,
    # not a silent overwrite. This is our answer to the "what if two
    # dispatchers assign the same request at once" question.
    version = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.id} - {self.customer_name} ({self.status})"

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())

    def apply_transition(self, new_status: str, changed_by, note: str = ""):
        """Advances status and writes the audit trail atomically-in-spirit.

        Raises ValueError on an illegal transition so callers (views/API)
        can turn that into a clean 400 response instead of corrupting state.
        """
        if not self.can_transition_to(new_status):
            raise ValueError(f"Cannot move from {self.status} to {new_status}")
        self.status = new_status
        self.version += 1
        self.save(update_fields=["status", "version", "updated_at"])
        StatusEvent.objects.create(
            request=self, status=new_status, changed_by=changed_by, note=note
        )


class StatusEvent(models.Model):
    """Append-only audit trail. Never edited or deleted -- only ever added to."""

    request = models.ForeignKey(DeliveryRequest, related_name="history", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=DeliveryRequest.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    note = models.CharField(max_length=200, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.request_id} -> {self.status} at {self.timestamp}"
