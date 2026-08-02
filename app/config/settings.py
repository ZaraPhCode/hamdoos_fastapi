from __future__ import annotations

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

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://ashauser:ashapass@db:5432/ashadb"

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