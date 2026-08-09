import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


PHONE_REGEX = re.compile(r"^1[3-9]\d{9}$")


class UserBase(BaseModel):
    email: Optional[str] = None
    username: str
    phone: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if v is None or v == "":
            return v
        if "@" not in v:
            raise ValueError("邮箱格式不正确")
        return v.lower()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v is None or v == "":
            return v
        if not PHONE_REGEX.match(v):
            raise ValueError("手机号格式不正确")
        return v


class UserCreate(UserBase):
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None

    def model_post_init(self, __context):
        if not self.email and not self.phone:
            raise ValueError("邮箱和手机号至少需要填写一项")


class UserLogin(BaseModel):
    identifier: str  # 邮箱或手机号
    password: str


class UserInDB(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
