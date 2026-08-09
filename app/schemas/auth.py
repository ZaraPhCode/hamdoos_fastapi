"""Pydantic schemas for authentication."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Email or phone number")
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: Optional[str] = None
    phone_number: str = Field(..., pattern=r"^09\d{9}$")
    password: str = Field(..., min_length=6)
    gender: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        return v


class VerifyPhoneRequest(BaseModel):
    phone_number: str = Field(..., pattern=r"^09\d{9}$")
    code: str = Field(..., min_length=4, max_length=10)


class ForgotPasswordRequest(BaseModel):
    username: str = Field(..., description="Email or phone number")


class ResetPasswordRequest(BaseModel):
    username: str = Field(..., description="Email or phone number")
    code: str = Field(..., min_length=4, max_length=10)
    new_password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: str = ""
    email: Optional[str] = None
    phone_number: Optional[str] = None
    gender: Optional[str] = None
    is_phone_confirmed: bool = False
    is_email_confirmed: bool = False
    roles: list[str] = []

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = None
    national_id: Optional[str] = None
    gender: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str