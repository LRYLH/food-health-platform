from pydantic import BaseModel, Field


class WechatLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)
    nickname: str | None = Field(default=None, max_length=64)


class WechatLoginResponse(BaseModel):
    access_token: str
    is_new_user: bool
