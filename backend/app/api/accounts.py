from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.models.user import User

from app.db.session import get_db
from app.models.account import Account

from fastapi import HTTPException
from app.services.balance import get_account_balance_cents

router = APIRouter(prefix="/accounts", tags=["accounts"])

@router.get("")
def list_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Account)
        .filter(Account.user_id == current_user.id)
        .all()
    )
@router.post("")
def create_account(
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    acct = Account(
        user_id=current_user.id,
        name=name,
    )

    db.add(acct)
    db.commit()
    db.refresh(acct)
    return acct

@router.get("/{account_id}/balance")
def get_balance(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    acct = (
        db.query(Account)
        .filter(Account.id == account_id, Account.user_id == current_user.id)
        .first()
    )
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")

    bal = get_account_balance_cents(db, account_id)
    return {"account_id": account_id, "currency": acct.currency, "balance_cents": bal}