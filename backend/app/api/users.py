from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.models.account import Account
from app.models.user import User
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    try:
        with db.begin():
            user = User(
                email=payload.email,
                hashed_password=hash_password(payload.password),
            )
            db.add(user)
            db.flush()

            external = Account(
                user_id=user.id,
                name="External",
                currency="USD",
                is_active=True,
                account_type="external",
            )
            db.add(external)

        db.refresh(user)
        return user

    except Exception:
        db.rollback()
        raise