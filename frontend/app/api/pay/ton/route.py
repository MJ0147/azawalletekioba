"""
TON blockchain payment route — creates Idia Coin (Jetton) payment requests via TON Connect.
"""
from __future__ import annotations

import os
import sys

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.api.pay.paymentHandler import create_ton_payment_request
from services.ton import TonServiceError

app = FastAPI()


class TonPayRequest(BaseModel):
    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    price_ngn: float = Field(gt=0, description="Price in Nigerian Naira")
    sender_address: str | None = Field(
        default=None,
        description="The connected TON Connect wallet address (raw or user-friendly).",
    )


@app.post("/api/pay/ton")
async def pay_with_ton(payload: TonPayRequest) -> JSONResponse:
    """
    Generate a TON Connect transaction payload for an Idia Coin Jetton transfer.
    The frontend uses this to open the TON Connect modal and submit the transaction.
    """
    try:
        result = await create_ton_payment_request(
            ngn_price=payload.price_ngn,
            product_name=payload.product_name,
            sender_address=payload.sender_address,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except TonServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Payment request failed.")

    return JSONResponse(result)
