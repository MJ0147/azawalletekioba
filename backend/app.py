import os
from dotenv import load_dotenv
from fastapi import FastAPI

# Load .env file when present (local dev); host environment variables override it
load_dotenv()

app = FastAPI()


@app.get("/api/hello")
def read_root():
    return {"message": "Hello from Python backend!"}


@app.get("/health")
def health():
    return {"status": "ok"}
