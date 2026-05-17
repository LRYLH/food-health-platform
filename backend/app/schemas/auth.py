from pydantic import BaseModel, Field


class WechatLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)
    nickname: str | None = Field(default=None, max_length=64)


class UserResponse(BaseModel):
    id: int
    email: str | None
    username: str
    phone: str | None
    openid: str | None
    nickname: str | None

    model_config = {"from_attributes": True}


class AuthSessionResponse(BaseModel):
    message: str
    expires_in_seconds: int
    refresh_expires_in_seconds: int
    user: UserResponse


class AuthMessageResponse(BaseModel):
    message: str
