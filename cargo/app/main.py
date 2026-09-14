from datetime import datetime
import random
import string

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Cargo Service")


class CargoQuoteRequest(BaseModel):
    distance_km: float = Field(gt=0)
    weight_kg: float = Field(gt=0)


class ShipmentStatus(BaseModel):
    shipment_id: str
    status: str
    eta_hours: int


class BookShipmentRequest(BaseModel):
    sender_name: str = Field(min_length=1)
    sender_address: str = Field(default="")
    recipient_name: str = Field(min_length=1)
    recipient_address: str = Field(default="")
    weight_kg: float = Field(gt=0)
    distance_km: float = Field(default=0.0, ge=0)
    description: str = Field(default="")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "cargo"}


@app.post("/quote")
def quote(payload: CargoQuoteRequest) -> dict[str, float]:
    base_fee = 5.0
    distance_rate = 0.4
    weight_rate = 0.2
    total = base_fee + payload.distance_km * distance_rate + payload.weight_kg * weight_rate
    return {"estimated_cost": round(total, 2)}


@app.get("/shipments/{shipment_id}")
def shipment_tracking(shipment_id: str) -> ShipmentStatus:
    return ShipmentStatus(shipment_id=shipment_id, status="in_transit", eta_hours=6)


@app.post("/book")
def book_shipment(payload: BookShipmentRequest) -> dict[str, object]:
    suffix = "".join(random.choices(string.digits, k=6))
    shipment_id = f"SHP-{datetime.utcnow().strftime('%Y%m%d')}-{suffix}"

    # Simple cost estimate
    base_fee = 5000.0
    cost = base_fee + payload.distance_km * 400 + payload.weight_kg * 200

    return {
        "shipment_id": shipment_id,
        "status": "booked",
        "sender_name": payload.sender_name,
        "recipient_name": payload.recipient_name,
        "weight_kg": payload.weight_kg,
        "estimated_cost_ngn": round(cost, 2),
        "eta_hours": max(2, int(payload.distance_km / 60)) if payload.distance_km > 0 else 24,
        "message": f"Shipment {shipment_id} booked. Use this ID to track your cargo.",
    }
