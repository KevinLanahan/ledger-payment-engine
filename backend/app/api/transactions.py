import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.account import Account
from app.models.ledger_entry import LedgerEntry
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionOut

router = APIRouter(prefix="/transactions", tags=["transactions"])


def get_balance_cents(db: Session, account_id: int) -> int:
    """
    Current balance = sum of all ledger entries for this account.
    """
    bal = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount_cents), 0))
        .filter(LedgerEntry.account_id == account_id)
        .scalar()
    )
    return int(bal or 0)


@router.post("", response_model=TransactionOut)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ---- basic validation ----
    if not payload.entries or len(payload.entries) < 2:
        raise HTTPException(status_code=422, detail="Transaction must have at least 2 entries")

    currency = payload.currency
    total = 0
    account_ids: set[int] = set()

    for e in payload.entries:
        if e.currency != currency:
            raise HTTPException(status_code=422, detail="All entries must match transaction currency")
        total += e.amount_cents
        account_ids.add(e.account_id)

    if total != 0:
        raise HTTPException(status_code=422, detail="Ledger entries must sum to 0")

    # ---- load & validate accounts (ownership, active, currency) ----
    accounts = (
        db.query(Account)
        .filter(Account.id.in_(account_ids), Account.user_id == current_user.id)
        .all()
    )
    if len(accounts) != len(account_ids):
        raise HTTPException(status_code=403, detail="One or more accounts not found or not owned by user")

    acct_by_id = {a.id: a for a in accounts}

    for e in payload.entries:
        acct = acct_by_id[e.account_id]
        if not acct.is_active:
            raise HTTPException(status_code=422, detail=f"Account {acct.id} is inactive")
        if acct.currency != currency:
            raise HTTPException(status_code=422, detail=f"Account {acct.id} currency mismatch")

    # ---- insufficient funds rule ----
    # If multiple entries hit the same account, combine them.
    delta_by_account = defaultdict(int)
    for e in payload.entries:
        delta_by_account[e.account_id] += e.amount_cents

    # If an account’s net change is negative, make sure it can afford it.
    for account_id, change in delta_by_account.items():
        if change < 0:
            current_balance = get_balance_cents(db, account_id)
            if current_balance + change < 0:
                raise HTTPException(
                    status_code=422,
                    detail=f"Insufficient funds in account {account_id}",
                )

    # ---- write transaction + ledger entries atomically ----
    try:
        tx = Transaction(
            user_id=current_user.id,
            type=payload.type,
            status="posted",
            idempotency_key=str(uuid.uuid4()),
        )
        db.add(tx)
        db.flush()  # ensures tx.id exists

        for e in payload.entries:
            db.add(
                LedgerEntry(
                    transaction_id=tx.id,
                    account_id=e.account_id,
                    amount_cents=e.amount_cents,
                    currency=currency,
                )
            )

        db.commit()
        db.refresh(tx)
        return tx

    except Exception:
        db.rollback()
        raise