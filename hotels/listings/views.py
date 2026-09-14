import random
import string
from datetime import datetime

from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking, Listing
from .serializers import BookingSerializer, ListingSerializer


def health_check(_request):
    return JsonResponse({"status": "ok", "service": "hotels"})


class ListingView(APIView):
    def get(self, request):
        city = request.query_params.get("city", "").strip()
        queryset = Listing.objects.all()
        if city:
            queryset = queryset.filter(city__icontains=city)
        queryset = queryset[:20]
        serializer = ListingSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ListingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = serializer.save()
        return Response(ListingSerializer(listing).data, status=201)


class BookingView(APIView):
    def post(self, request):
        data = request.data
        required = ["hotel_name", "check_in", "check_out"]
        for field in required:
            if not data.get(field):
                return Response({"error": f"'{field}' is required."}, status=400)

        suffix = "".join(random.choices(string.digits, k=6))
        booking_ref = f"BK-{datetime.utcnow().strftime('%Y%m%d')}-{suffix}"

        booking = Booking.objects.create(
            booking_ref=booking_ref,
            hotel_id=str(data.get("hotel_id", data["hotel_name"]))[:200],
            hotel_name=data["hotel_name"][:200],
            check_in=data["check_in"],
            check_out=data["check_out"],
            nights=int(data.get("nights", 1)),
            price_per_night=float(data.get("price_per_night", 0)),
            chain=str(data.get("chain", "ton"))[:20],
        )
        return Response(BookingSerializer(booking).data, status=201)
