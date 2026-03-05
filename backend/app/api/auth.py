# app/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut
from app.schemas.auth import Token
from app.models.account import Account
from app.core.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        with db.begin():
            user = User(
                email=payload.email,
                hashed_password=hash_password(payload.password),
            )
            db.add(user)
            db.flush()  # ensures user.id exists without committing yet

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

@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token(subject=user.email)
    return {"access_token": token, "token_type": "bearer"}