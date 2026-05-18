from datetime import date, datetime

from pydantic import BaseModel, Field


class HealthProfileBase(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    gender: str | None = Field(default=None, max_length=16)
    birthday: date | None = None
    height_cm: float | None = Field(default=None, ge=30, le=250)
    weight_kg: float | None = Field(default=None, ge=1, le=300)
    chronic_diseases: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    dietary_preferences: list[str] = Field(default_factory=list)
    medication_notes: str | None = None
    emergency_contact: str | None = Field(default=None, max_length=64)


class HealthProfileCreate(HealthProfileBase):
    pass


class HealthProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    gender: str | None = Field(default=None, max_length=16)
    birthday: date | None = None
    height_cm: float | None = Field(default=None, ge=30, le=250)
    weight_kg: float | None = Field(default=None, ge=1, le=300)
    chronic_diseases: list[str] | None = None
    allergies: list[str] | None = None
    dietary_preferences: list[str] | None = None
    medication_notes: str | None = None
    emergency_contact: str | None = Field(default=None, max_length=64)


class HealthProfileResponse(HealthProfileBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserProfilePayload(BaseModel):
    allergens: list[str] = Field(default_factory=list)
    chronic_diseases: list[str] = Field(default_factory=list)


class UserProfileResponse(UserProfilePayload):
    pass
