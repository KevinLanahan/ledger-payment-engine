from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ledger_entry import LedgerEntry


def get_account_balance_cents(db: Session, account_id: int) -> int:
    stmt = select(func.coalesce(func.sum(LedgerEntry.amount_cents), 0)).where(
        LedgerEntry.account_id == account_id
    )
    return int(db.execute(stmt).scalar_one())