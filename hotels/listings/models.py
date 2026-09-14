from django.db import models


class Listing(models.Model):
    title = models.CharField(max_length=160)
    city = models.CharField(max_length=100)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, default="")
    image_url = models.URLField(blank=True, default="")
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    available = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.title


class Booking(models.Model):
    booking_ref = models.CharField(max_length=30, unique=True)
    hotel_id = models.CharField(max_length=200)
    hotel_name = models.CharField(max_length=200)
    check_in = models.DateField()
    check_out = models.DateField()
    nights = models.PositiveIntegerField(default=1)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    chain = models.CharField(max_length=20, default="ton")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.booking_ref
