import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.account import Account
from app.models.ledger_entry import LedgerEntry
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import (
    AccountTransactionOut,
    LedgerEntryOut,
    TransactionCreate,
    TransactionOut,
)
from app.services.balance import get_account_balance_cents

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("", response_model=TransactionOut)
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not payload.entries or len(payload.entries) < 2:
        raise HTTPException(
            status_code=422,
            detail="Transaction must have at least 2 entries",
        )

    currency = payload.currency
    total = 0
    account_ids: set[int] = set()

    for entry in payload.entries:
        if entry.currency != currency:
            raise HTTPException(
                status_code=422,
                detail="All entries must match transaction currency",
            )

        total += entry.amount_cents
        account_ids.add(entry.account_id)

    if total != 0:
        raise HTTPException(
            status_code=422,
            detail="Ledger entries must sum to 0",
        )

    accounts = (
        db.query(Account)
        .filter(
            Account.id.in_(account_ids),
            Account.user_id == current_user.id,
        )
        .all()
    )

    if len(accounts) != len(account_ids):
        raise HTTPException(
            status_code=403,
            detail="One or more accounts not found or not owned by user",
        )

    acct_by_id = {acct.id: acct for acct in accounts}

    for entry in payload.entries:
        acct = acct_by_id[entry.account_id]

        if not acct.is_active:
            raise HTTPException(
                status_code=422,
                detail=f"Account {acct.id} is inactive",
            )

        if acct.currency != currency:
            raise HTTPException(
                status_code=422,
                detail=f"Account {acct.id} currency mismatch",
            )

    delta_by_account = defaultdict(int)
    for entry in payload.entries:
        delta_by_account[entry.account_id] += entry.amount_cents

    for account_id, change in delta_by_account.items():
        if change < 0:
            current_balance = get_account_balance_cents(db, account_id)
            if current_balance + change < 0:
                raise HTTPException(
                    status_code=422,
                    detail=f"Insufficient funds in account {account_id}",
                )

    try:
        tx = Transaction(
            user_id=current_user.id,
            type=payload.type,
            status="posted",
            idempotency_key=str(uuid.uuid4()),
            description=payload.description,
        )
        db.add(tx)
        db.flush()

        for entry in payload.entries:
            db.add(
                LedgerEntry(
                    transaction_id=tx.id,
                    account_id=entry.account_id,
                    amount_cents=entry.amount_cents,
                    currency=currency,
                )
            )

        db.commit()

        tx = (
            db.query(Transaction)
            .options(selectinload(Transaction.entries))
            .filter(Transaction.id == tx.id)
            .first()
        )

        return tx

    except Exception:
        db.rollback()
        raise


@router.get("/account/{account_id}", response_model=list[AccountTransactionOut])
def list_account_transactions(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    acct = (
        db.query(Account)
        .filter(
            Account.id == account_id,
            Account.user_id == current_user.id,
        )
        .first()
    )

    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")

    transactions = (
        db.query(Transaction)
        .join(LedgerEntry, LedgerEntry.transaction_id == Transaction.id)
        .options(selectinload(Transaction.entries))
        .filter(
            Transaction.user_id == current_user.id,
            LedgerEntry.account_id == account_id,
        )
        .order_by(Transaction.created_at.desc())
        .all()
    )

    result: list[AccountTransactionOut] = []

    for tx in transactions:
        net_amount_cents = sum(
            entry.amount_cents
            for entry in tx.entries
            if entry.account_id == account_id
        )

        result.append(
            AccountTransactionOut(
                transaction_id=tx.id,
                type=tx.type,
                status=tx.status,
                idempotency_key=tx.idempotency_key,
                description=tx.description,
                created_at=tx.created_at,
                net_amount_cents=net_amount_cents,
                entries=[
                    LedgerEntryOut.model_validate(entry)
                    for entry in tx.entries
                ],
            )
        )

    return result