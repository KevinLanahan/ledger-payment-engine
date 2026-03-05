from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_transactions_idempotency_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # "deposit" | "withdraw" | "transfer"
    type: Mapped[str] = mapped_column(String(20), nullable=False)

    # "posted" | "failed" (you can add "pending" later)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="posted")

    # client-supplied idempotency key (header)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="transactions")
    entries = relationship(
        "LedgerEntry",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )