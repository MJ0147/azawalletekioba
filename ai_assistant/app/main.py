import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Iyobo Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


GOOGLE_CLOUD_PYTHON_LIBRARIES_SOURCE = os.getenv(
    "GOOGLE_CLOUD_PYTHON_LIBRARIES_SOURCE",
    "",
)


@app.get("/health")
def health_check() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "iyobo",
        "google_cloud_source_configured": bool(GOOGLE_CLOUD_PYTHON_LIBRARIES_SOURCE),
    }


@app.get("/config/runtime")
def runtime_config() -> dict[str, str]:
    return {
        "google_cloud_python_libraries_source": GOOGLE_CLOUD_PYTHON_LIBRARIES_SOURCE,
    }


@app.post("/chat")
def chat(payload: ChatRequest) -> dict[str, str]:
    user_message = payload.message.strip()
    return {
        "reply": f"Iyobo received: {user_message}",
        "model": "iyobo-baseline-v1",
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
