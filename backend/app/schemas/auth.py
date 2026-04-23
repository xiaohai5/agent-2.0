from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: str = Field(..., min_length=5, max_length=120)
    password: str = Field(..., min_length=6, max_length=64)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        email = value.strip()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("邮箱格式不正确")
        return email


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=64)


class ChangePasswordRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    old_password: str = Field(..., min_length=6, max_length=64)
    new_password: str = Field(..., min_length=6, max_length=64)
    confirm_password: str = Field(..., min_length=6, max_length=64)

    @model_validator(mode="after")
    def validate_passwords(self) -> "ChangePasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("两次输入的新密码不一致")
        return self


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class UserProfileData(BaseModel):
    id: int
    username: str
    email: str


class MessageData(BaseModel):
    message: str
