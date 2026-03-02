from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(
    title="Ledger Payment Engine",
    version="0.1.0"
)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "db": settings.DATABASE_URL.split("@")[-1]
    }