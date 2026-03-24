import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.account import Account
from app.models.ledger_entry import LedgerEntry
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transfer import TransferCreate, TransferOut, TransferLedgerEntryOut
from app.services.balance import get_account_balance_cents
from app.services.audit_service import log_audit_event

router = APIRouter(prefix="/transfers", tags=["transfers"])


@router.post("", response_model=TransferOut, status_code=status.HTTP_201_CREATED)
def create_transfer(
    payload: TransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.from_account_id == payload.to_account_id:
        raise HTTPException(
            status_code=422,
            detail="Source and destination accounts must be different",
        )

    accounts = (
        db.query(Account)
        .filter(
            Account.id.in_([payload.from_account_id, payload.to_account_id]),
            Account.user_id == current_user.id,
            Account.account_type == "user",
        )
        .all()
    )

    if len(accounts) != 2:
        raise HTTPException(
            status_code=404,
            detail="One or both accounts not found",
        )

    account_by_id = {acct.id: acct for acct in accounts}

    from_account = account_by_id[payload.from_account_id]
    to_account = account_by_id[payload.to_account_id]

    if not from_account.is_active:
        raise HTTPException(status_code=422, detail="Source account is inactive")

    if not to_account.is_active:
        raise HTTPException(status_code=422, detail="Destination account is inactive")

    if from_account.currency != to_account.currency:
        raise HTTPException(
            status_code=422,
            detail="Source and destination accounts must use the same currency",
        )

    current_balance = get_account_balance_cents(db, from_account.id)
    if current_balance < payload.amount_cents:
        raise HTTPException(status_code=422, detail="Insufficient funds")

    try:
        tx = Transaction(
            user_id=current_user.id,
            type="transfer",
            status="posted",
            idempotency_key=str(uuid.uuid4()),
            description=payload.description,
        )
        db.add(tx)
        db.flush()

        db.add(
            LedgerEntry(
                transaction_id=tx.id,
                account_id=from_account.id,
                amount_cents=-payload.amount_cents,
                currency=from_account.currency,
            )
        )
        db.add(
            LedgerEntry(
                transaction_id=tx.id,
                account_id=to_account.id,
                amount_cents=payload.amount_cents,
                currency=to_account.currency,
            )
        )
        
        log_audit_event(
            db,
            user_id=current_user.id,
            action="transfer_created",
            entity_type="transaction",
            entity_id=tx.id,
            details={
                "from_account_id": from_account.id,
                "to_account_id": to_account.id,
                "amount_cents": payload.amount_cents,
                "description": payload.description,
                "transaction_type": "transfer",
            },
        )
        

        db.commit()

        tx = (
            db.query(Transaction)
            .options(selectinload(Transaction.entries))
            .filter(Transaction.id == tx.id)
            .first()
        )

        return TransferOut(
            transaction_id=tx.id,
            user_id=tx.user_id,
            type=tx.type,
            status=tx.status,
            idempotency_key=tx.idempotency_key,
            description=tx.description,
            created_at=tx.created_at,
            from_account_id=from_account.id,
            to_account_id=to_account.id,
            amount_cents=payload.amount_cents,
            entries=[
                TransferLedgerEntryOut.model_validate(entry)
                for entry in tx.entries
            ],
        )

    except Exception:
        db.rollback()
        raise