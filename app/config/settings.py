from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Asha Shop"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "replace-with-a-strong-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # Database — fetched from the .env file. Either set DATABASE_URL directly,
    # or the individual POSTGRES_* components; DATABASE_URL takes precedence
    # and is otherwise assembled from the components (matching the postgres
    # container env in docker-compose).
    POSTGRES_USER: str = "ashauser"
    POSTGRES_PASSWORD: str = "ashapass"
    POSTGRES_DB: str = "ashadb"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str = ""

    @model_validator(mode="after")
    def _build_database_url(self):
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self

    # Media: the migration stores relative paths like "Media/laser/...". The app
    # serves them from /media (bundled copy or mounted .NET wwwroot/Media). For
    # files not present locally (e.g. fresh VPS before Media is copied over),
    # set MEDIA_BASE_URL to the old site that still hosts the files, e.g.
    #   MEDIA_BASE_URL=https://hamdoos.ir
    # and /media/... requests will fall back to that origin.
    MEDIA_BASE_URL: str = "https://hamdoos.ir"

    # ZarinPal
    ZARINPAL_MERCHANT_ID: str = ""
    ZARINPAL_SITE_URL: str = "https://hamdoos.ir"
    ZARINPAL_CALLBACK_URL: str = "/shop/order/return/"

    # SMS - Provider selection
    SMS_PROVIDER: str = "Melipayamak"

    # FarazSMS
    FARAZSMS_ENDPOINT: str = ""
    FARAZSMS_USERNAME: str = ""
    FARAZSMS_PASSWORD: str = ""
    FARAZSMS_FROM_NUMBER: str = ""
    FARAZSMS_PATTERN_VERIFICATION: str = ""
    FARAZSMS_PATTERN_PRODUCT: str = ""
    FARAZSMS_PATTERN_ORDER: str = ""

    # Melipayamak
    MELIPAYAMAK_ENDPOINT: str = ""
    MELIPAYAMAK_USERNAME: str = ""
    MELIPAYAMAK_PASSWORD: str = ""
    MELIPAYAMAK_FROM_NUMBER: str = ""
    MELIPAYAMAK_PATTERN_VERIFICATION: str = ""
    MELIPAYAMAK_PATTERN_PRODUCT: str = ""
    MELIPAYAMAK_PATTERN_ORDER: str = ""

    # Bale
    BALE_ENDPOINT: str = ""
    BALE_ACCESS_KEY: str = ""
    BALE_BOT_ID: int = 0

    # Email (Outlook SMTP)
    EMAIL_HOST: str = "smtp.office365.com"
    EMAIL_PORT: int = 587
    EMAIL_USERNAME: str = ""
    EMAIL_PASSWORD: str = ""
    EMAIL_FROM: str = ""
    EMAIL_USE_TLS: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()