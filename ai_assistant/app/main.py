import logging
import os
import sys
from typing import Optional, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Setup structured logging for Cloud Run
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("iyobo-service")

app = FastAPI(title="Iyobo AI Assistant", description="AI Service for Ekioba E-commerce")

# Allow CORS for frontend interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's input message")
    user_id: Optional[str] = Field(None, description="Optional user ID for context")
    context: Optional[Dict] = Field(None, description="Additional context (e.g., cart items)")


class ChatResponse(BaseModel):
    reply: str
    intent: Optional[str] = None


@app.get("/", tags=["Health"])
def root():
    """Root endpoint for basic connectivity check."""
    return {"service": "Iyobo AI Assistant", "status": "running"}


@app.get("/health", tags=["Health"])
def health_check():
    """Health check for Cloud Run probes."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(payload: ChatRequest):
    """
    Process a chat message.
    Currently acts as a placeholder for LLM integration.
    """
    logger.info(f"Received message from user {payload.user_id}: {payload.message}")

    user_message = payload.message.strip().lower()
    intent = "general"
    reply = f"I am Iyobo, your shopping assistant. You said: {payload.message}"

    # Basic intent recognition for E-commerce context
    if "pay" in user_message or "coin" in user_message or "idia" in user_message:
        reply = "You can pay using Idia Coin via TON or Solana blockchains. Do you need help with your wallet?"
        intent = "payment_help"
    elif "order" in user_message or "cart" in user_message:
        reply = "I can help you find items or check your order status."
        intent = "order_help"

    return {
        "reply": reply,
        "intent": intent,
    }


if __name__ == "__main__":
    # Cloud Run injects the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Iyobo AI Service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
