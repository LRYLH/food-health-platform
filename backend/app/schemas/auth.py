from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    verification_code: str = Field(min_length=4, max_length=12)


class SendEmailCodeRequest(BaseModel):
    email: EmailStr


class SendEmailCodeResponse(BaseModel):
    message: str
    expires_in_seconds: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class WechatLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)
    nickname: str | None = Field(default=None, max_length=64)


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    phone: str | None
    openid: str | None
    nickname: str | None

    model_config = {"from_attributes": True}


class RegisterResponse(BaseModel):
    message: str
    user: UserResponse


class AuthSessionResponse(BaseModel):
    message: str
    expires_in_seconds: int
    refresh_expires_in_seconds: int
    user: UserResponse


class AuthMessageResponse(BaseModel):
    message: str
