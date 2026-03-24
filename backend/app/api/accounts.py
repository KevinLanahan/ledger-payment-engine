from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.account import Account
from app.models.ledger_entry import LedgerEntry
from app.models.transaction import Transaction
from app.models.user import User
from app.services.balance import get_account_balance_cents
from app.services.audit_service import log_audit_event
import uuid

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountCreate(BaseModel):
    name: str


class AccountOut(BaseModel):
    id: int
    name: str
    currency: str
    is_active: bool
    account_type: str
    balance_cents: int

    class Config:
        from_attributes = True


class AccountBalanceOut(BaseModel):
    account_id: int
    currency: str
    balance_cents: int


class MoneyMovementRequest(BaseModel):
    amount_cents: int = Field(..., gt=0, description="Positive integer amount in cents")
    description: str | None = None


def get_user_visible_account_or_404(
    db: Session,
    current_user: User,
    account_id: int,
) -> Account:
    acct = (
        db.query(Account)
        .filter(
            Account.id == account_id,
            Account.user_id == current_user.id,
            Account.account_type == "user",
        )
        .first()
    )

    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")

    if not acct.is_active:
        raise HTTPException(status_code=422, detail="Account is inactive")

    return acct


def get_external_account_or_500(db: Session, current_user: User) -> Account:
    external = (
        db.query(Account)
        .filter(
            Account.user_id == current_user.id,
            Account.account_type == "external",
        )
        .first()
    )

    if not external:
        raise HTTPException(
            status_code=500,
            detail="External funding account missing for user",
        )

    if not external.is_active:
        raise HTTPException(
            status_code=422,
            detail="External funding account is inactive",
        )

    return external


def build_transaction_response(tx: Transaction):
    return {
        "id": tx.id,
        "user_id": tx.user_id,
        "type": tx.type,
        "status": tx.status,
        "idempotency_key": tx.idempotency_key,
        "description": tx.description,
        "created_at": tx.created_at,
        "entries": [
            {
                "id": entry.id,
                "account_id": entry.account_id,
                "amount_cents": entry.amount_cents,
                "currency": entry.currency,
                "created_at": entry.created_at,
            }
            for entry in tx.entries
        ],
    }


@router.get("", response_model=list[AccountOut])
def list_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accounts = (
        db.query(Account)
        .filter(
            Account.user_id == current_user.id,
            Account.account_type == "user",
        )
        .order_by(Account.id.asc())
        .all()
    )

    return [
        AccountOut(
            id=acct.id,
            name=acct.name,
            currency=acct.currency,
            is_active=acct.is_active,
            account_type=acct.account_type,
            balance_cents=get_account_balance_cents(db, acct.id),
        )
        for acct in accounts
    ]


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        acct = Account(
            user_id=current_user.id,
            name=payload.name,
            currency="USD",
            is_active=True,
            account_type="user",
        )

        db.add(acct)
        db.flush()

        log_audit_event(
            db,
            user_id=current_user.id,
            action="account_created",
            entity_type="account",
            entity_id=acct.id,
            details={
                "account_name": acct.name,
                "currency": acct.currency,
                "account_type": acct.account_type,
            },
        )

        db.commit()
        db.refresh(acct)

        return AccountOut(
            id=acct.id,
            name=acct.name,
            currency=acct.currency,
            is_active=acct.is_active,
            account_type=acct.account_type,
            balance_cents=0,
        )

    except Exception:
        db.rollback()
        raise

@router.get("/{account_id}/balance", response_model=AccountBalanceOut)
def get_balance(
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

    bal = get_account_balance_cents(db, account_id)

    return AccountBalanceOut(
        account_id=account_id,
        currency=acct.currency,
        balance_cents=bal,
    )


@router.post("/{account_id}/deposit", status_code=status.HTTP_201_CREATED)
def deposit_to_account(
    account_id: int,
    payload: MoneyMovementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_account = get_user_visible_account_or_404(db, current_user, account_id)
    external_account = get_external_account_or_500(db, current_user)

    if user_account.currency != external_account.currency:
        raise HTTPException(status_code=422, detail="Currency mismatch between accounts")

    try:
        tx = Transaction(
            user_id=current_user.id,
            type="deposit",
            status="posted",
            idempotency_key=str(uuid.uuid4()),
            description=payload.description,
        )
        db.add(tx)
        db.flush()

        db.add(
            LedgerEntry(
                transaction_id=tx.id,
                account_id=user_account.id,
                amount_cents=payload.amount_cents,
                currency=user_account.currency,
            )
        )
        db.add(
            LedgerEntry(
                transaction_id=tx.id,
                account_id=external_account.id,
                amount_cents=-payload.amount_cents,
                currency=external_account.currency,
            )
        )
        log_audit_event(
            db,
            user_id=current_user.id,
            action="deposit_created",
            entity_type="transaction",
            entity_id=tx.id,
            details={
                "account_id": user_account.id,
                "external_account_id": external_account.id,
                "amount_cents": payload.amount_cents,
                "description": payload.description,
                "transaction_type": "deposit",
            },
        )

        db.commit()

        tx = (
            db.query(Transaction)
            .options(selectinload(Transaction.entries))
            .filter(Transaction.id == tx.id)
            .first()
        )

        return build_transaction_response(tx)

    except Exception:
        db.rollback()
        raise


@router.post("/{account_id}/withdraw", status_code=status.HTTP_201_CREATED)
def withdraw_from_account(
    account_id: int,
    payload: MoneyMovementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_account = get_user_visible_account_or_404(db, current_user, account_id)
    external_account = get_external_account_or_500(db, current_user)

    if user_account.currency != external_account.currency:
        raise HTTPException(status_code=422, detail="Currency mismatch between accounts")

    current_balance = get_account_balance_cents(db, user_account.id)
    if current_balance < payload.amount_cents:
        raise HTTPException(status_code=422, detail="Insufficient funds")

    try:
        tx = Transaction(
            user_id=current_user.id,
            type="withdraw",
            status="posted",
            idempotency_key=str(uuid.uuid4()),
            description=payload.description,
        )
        db.add(tx)
        db.flush()

        db.add(
            LedgerEntry(
                transaction_id=tx.id,
                account_id=user_account.id,
                amount_cents=-payload.amount_cents,
                currency=user_account.currency,
            )
        )
        db.add(
            LedgerEntry(
                transaction_id=tx.id,
                account_id=external_account.id,
                amount_cents=payload.amount_cents,
                currency=external_account.currency,
            )
        )
        log_audit_event(
            db,
            user_id=current_user.id,
            action="withdrawal_created",
            entity_type="transaction",
            entity_id=tx.id,
            details={
                "account_id": user_account.id,
                "external_account_id": external_account.id,
                "amount_cents": payload.amount_cents,
                "description": payload.description,
                "transaction_type": "withdraw",
            },
        )

        db.commit()

        tx = (
            db.query(Transaction)
            .options(selectinload(Transaction.entries))
            .filter(Transaction.id == tx.id)
            .first()
        )

        return build_transaction_response(tx)

    except Exception:
        db.rollback()
        raise