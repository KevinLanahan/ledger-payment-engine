from fastapi import FastAPI
from app.core.config import settings

from app.api.users import router as users_router
from app.api.accounts import router as accounts_router
from app.api.auth import router as auth_router
from app.api.transactions import router as transactions_router

app = FastAPI(
    title="Ledger Payment Engine",
    version="0.1.0"
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(accounts_router)
app.include_router(transactions_router)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "db": settings.DATABASE_URL.split("@")[-1]
    }

@app.get("/")
def root():
    return {"message": "Ledger Payment Engine API"}