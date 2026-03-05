from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root (ledger-payment-engine/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT / Auth
    SECRET_KEY: str = "dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        extra="ignore",
    )


settings = Settings()