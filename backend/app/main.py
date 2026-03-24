from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.users import router as users_router
from app.api.accounts import router as accounts_router
from app.api.auth import router as auth_router
from app.api.transactions import router as transactions_router
from app.api.transfer import router as transfers_router
from app.api.audit_logs import router as audit_logs_router

app = FastAPI(
    title="Ledger Payment Engine",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(accounts_router)
app.include_router(transactions_router)
app.include_router(transfers_router)
app.include_router(audit_logs_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "db": settings.DATABASE_URL.split("@")[-1]
    }


@app.get("/")
def root():
    return {"message": "Ledger Payment Engine API"}