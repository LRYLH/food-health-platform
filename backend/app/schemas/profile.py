from pydantic import BaseModel, Field


class UserProfilePayload(BaseModel):
    allergens: list[str] = Field(default_factory=list)
    chronic_diseases: list[str] = Field(default_factory=list)


class UserProfileResponse(UserProfilePayload):
    pass
