from fastapi import FastAPI


app = FastAPI(title="python-api")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "ok", "service": "python-api"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}
