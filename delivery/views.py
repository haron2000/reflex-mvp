from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.views import View

from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DeliveryRequest, UserProfile
from .serializers import (
    AssignSerializer,
    CreateDeliveryRequestSerializer,
    DeliveryRequestSerializer,
    RiderSerializer,
    ScanSerializer,
)


# ---------- Auth / dashboard routing ----------

class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return render(request, "delivery/login.html", {"form": AuthenticationForm()})

    def post(self, request):
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            auth_login(request, form.get_user())
            return redirect("dashboard")
        return render(request, "delivery/login.html", {"form": form})


@login_required
def dashboard(request):
    """Routes each user to the template that matches their role.

    Falls back to a 'no role assigned' notice rather than crashing -- an
    admin-created user without a profile shouldn't get a 500.
    """
    profile = getattr(request.user, "profile", None)
    if profile is None:
        return render(request, "delivery/no_role.html")

    if profile.role == UserProfile.Role.RETAILER:
        return render(request, "delivery/retailer_dashboard.html")
    if profile.role == UserProfile.Role.DISPATCHER:
        return render(request, "delivery/dispatcher_dashboard.html")
    if profile.role == UserProfile.Role.RIDER:
        return render(request, "delivery/rider_dashboard.html")
    return render(request, "delivery/no_role.html")


# ---------- API ----------

def _role(user):
    profile = getattr(user, "profile", None)
    return profile.role if profile else None


class DeliveryRequestListCreateAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = _role(request.user)
        qs = DeliveryRequest.objects.select_related("retailer", "assigned_rider").prefetch_related("history")

        if role == UserProfile.Role.RETAILER:
            qs = qs.filter(retailer=request.user)
        elif role == UserProfile.Role.RIDER:
            qs = qs.filter(assigned_rider=request.user).exclude(status=DeliveryRequest.Status.DELIVERED)
        elif role == UserProfile.Role.DISPATCHER:
            pass  # dispatcher sees everything open + assigned
        else:
            return Response({"detail": "No role assigned."}, status=http_status.HTTP_403_FORBIDDEN)

        return Response(DeliveryRequestSerializer(qs, many=True).data)

    def post(self, request):
        if _role(request.user) != UserProfile.Role.RETAILER:
            return Response({"detail": "Only retailer staff can log a delivery."}, status=http_status.HTTP_403_FORBIDDEN)

        serializer = CreateDeliveryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(retailer=request.user)
        return Response(DeliveryRequestSerializer(obj).data, status=http_status.HTTP_201_CREATED)


class RiderListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        riders = User.objects.filter(profile__role=UserProfile.Role.RIDER, profile__is_active_rider=True)
        return Response(RiderSerializer(riders, many=True).data)


class AssignRequestAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if _role(request.user) != UserProfile.Role.DISPATCHER:
            return Response({"detail": "Only dispatchers can assign."}, status=http_status.HTTP_403_FORBIDDEN)

        serializer = AssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            obj = DeliveryRequest.objects.get(pk=pk)
        except DeliveryRequest.DoesNotExist:
            return Response({"detail": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)

        # Optimistic-locking check: someone else may have already assigned
        # this while the dispatcher's screen was stale.
        if obj.version != serializer.validated_data["version"]:
            return Response(
                {"detail": "This request was already updated by someone else. Refresh and try again."},
                status=http_status.HTTP_409_CONFLICT,
            )

        try:
            rider = User.objects.get(pk=serializer.validated_data["rider_id"], profile__role=UserProfile.Role.RIDER)
        except User.DoesNotExist:
            return Response({"detail": "Rider not found."}, status=http_status.HTTP_400_BAD_REQUEST)

        obj.assigned_rider = rider
        obj.save(update_fields=["assigned_rider"])
        try:
            obj.apply_transition(DeliveryRequest.Status.ASSIGNED, changed_by=request.user, note=f"Assigned to {rider.username}")
        except ValueError as e:
            return Response({"detail": str(e)}, status=http_status.HTTP_400_BAD_REQUEST)

        return Response(DeliveryRequestSerializer(obj).data)


class ScanAPI(APIView):
    """Rider scans a QR code (or types the token as a fallback) to advance status.

    Server-validated: we look the token up ourselves and check the state
    machine allows the move. A forged or reused code that doesn't match a
    request awaiting exactly that transition is rejected.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if _role(request.user) != UserProfile.Role.RIDER:
            return Response({"detail": "Only riders can scan."}, status=http_status.HTTP_403_FORBIDDEN)

        serializer = ScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            obj = DeliveryRequest.objects.get(qr_token=serializer.validated_data["qr_token"])
        except DeliveryRequest.DoesNotExist:
            return Response({"detail": "No delivery matches that code."}, status=http_status.HTTP_404_NOT_FOUND)

        if obj.assigned_rider_id != request.user.id:
            return Response({"detail": "This delivery isn't assigned to you."}, status=http_status.HTTP_403_FORBIDDEN)

        if obj.version != serializer.validated_data["version"]:
            return Response(
                {"detail": "Status changed elsewhere. Refresh and try again."},
                status=http_status.HTTP_409_CONFLICT,
            )

        next_status = {
            DeliveryRequest.Status.ASSIGNED: DeliveryRequest.Status.PICKED_UP,
            DeliveryRequest.Status.PICKED_UP: DeliveryRequest.Status.DELIVERED,
        }.get(obj.status)

        if next_status is None:
            return Response(
                {"detail": f"No valid next step from {obj.get_status_display()}."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            obj.apply_transition(next_status, changed_by=request.user, note="Confirmed via QR scan")
        except ValueError as e:
            return Response({"detail": str(e)}, status=http_status.HTTP_400_BAD_REQUEST)

        return Response(DeliveryRequestSerializer(obj).data)


@login_required
def qr_image(request, pk):
    """Serves the QR code PNG for a given delivery request, generated on the fly."""
    import io
    import qrcode
    from django.http import HttpResponse

    try:
        obj = DeliveryRequest.objects.get(pk=pk)
    except DeliveryRequest.DoesNotExist:
        return HttpResponse(status=404)

    img = qrcode.make(str(obj.qr_token))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")
