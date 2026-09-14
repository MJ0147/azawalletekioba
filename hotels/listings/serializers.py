from rest_framework import serializers

from .models import Booking, Listing


class ListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = ["id", "title", "city", "price_per_night", "description", "image_url", "rating", "available"]


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ["booking_ref", "hotel_id", "hotel_name", "check_in", "check_out", "nights", "price_per_night", "chain", "created_at"]
