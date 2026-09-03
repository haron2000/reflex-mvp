from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    path("api/requests/", views.DeliveryRequestListCreateAPI.as_view(), name="api_requests"),
    path("api/requests/<int:pk>/assign/", views.AssignRequestAPI.as_view(), name="api_assign"),
    path("api/riders/", views.RiderListAPI.as_view(), name="api_riders"),
    path("api/scan/", views.ScanAPI.as_view(), name="api_scan"),

    path("qr/<int:pk>.png", views.qr_image, name="qr_image"),
]
