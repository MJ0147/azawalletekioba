from django.contrib import admin
from django.urls import path

from listings.views import BookingView, ListingView, health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health"),
    path("api/listings/", ListingView.as_view(), name="listings"),
    path("api/bookings/", BookingView.as_view(), name="bookings"),
]
