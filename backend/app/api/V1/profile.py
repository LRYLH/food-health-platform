from datetime import date

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.user import User
from ...schemas.profile import (
    HealthProfileCreate,
    HealthProfileResponse,
    HealthProfileUpdate,
)
from ...services.profile_service import delete_profile, get_profile, upsert_profile


router = APIRouter(prefix="/profile", tags=["profile"])


def _normalize_query_list(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    normalized: list[str] = []
    for value in values:
        normalized.extend(item.strip() for item in value.split(",") if item.strip())
    return normalized


def _profile_payload_from_query(
    *,
    update: bool,
    name: str | None,
    gender: str | None,
    birthday: date | None,
    height_cm: float | None,
    weight_kg: float | None,
    chronic_diseases: list[str] | None,
    allergies: list[str] | None,
    dietary_preferences: list[str] | None,
    medication_notes: str | None,
    emergency_contact: str | None,
) -> HealthProfileCreate | HealthProfileUpdate:
    data = {
        "name": name,
        "gender": gender,
        "birthday": birthday,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "chronic_diseases": _normalize_query_list(chronic_diseases),
        "allergies": _normalize_query_list(allergies),
        "dietary_preferences": _normalize_query_list(dietary_preferences),
        "medication_notes": medication_notes,
        "emergency_contact": emergency_contact,
    }
    if update:
        return HealthProfileUpdate(**{key: value for key, value in data.items() if value is not None})
    return HealthProfileCreate(**{key: value for key, value in data.items() if value is not None})


@router.get("", response_model=HealthProfileResponse)
def read_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HealthProfileResponse:
    return get_profile(db, current_user)


@router.post("", response_model=HealthProfileResponse, status_code=201)
def create_or_replace_profile(
    payload: HealthProfileCreate | None = Body(default=None),
    name: str | None = Query(default=None, max_length=64),
    gender: str | None = Query(default=None, max_length=16),
    birthday: date | None = Query(default=None),
    height_cm: float | None = Query(default=None, ge=30, le=250),
    weight_kg: float | None = Query(default=None, ge=1, le=300),
    chronic_diseases: list[str] | None = Query(default=None),
    allergies: list[str] | None = Query(default=None),
    dietary_preferences: list[str] | None = Query(default=None),
    medication_notes: str | None = Query(default=None),
    emergency_contact: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HealthProfileResponse:
    profile_payload = payload or _profile_payload_from_query(
        update=False,
        name=name,
        gender=gender,
        birthday=birthday,
        height_cm=height_cm,
        weight_kg=weight_kg,
        chronic_diseases=chronic_diseases,
        allergies=allergies,
        dietary_preferences=dietary_preferences,
        medication_notes=medication_notes,
        emergency_contact=emergency_contact,
    )
    return upsert_profile(db, current_user, profile_payload)


@router.patch("", response_model=HealthProfileResponse)
def update_profile(
    payload: HealthProfileUpdate | None = Body(default=None),
    name: str | None = Query(default=None, max_length=64),
    gender: str | None = Query(default=None, max_length=16),
    birthday: date | None = Query(default=None),
    height_cm: float | None = Query(default=None, ge=30, le=250),
    weight_kg: float | None = Query(default=None, ge=1, le=300),
    chronic_diseases: list[str] | None = Query(default=None),
    allergies: list[str] | None = Query(default=None),
    dietary_preferences: list[str] | None = Query(default=None),
    medication_notes: str | None = Query(default=None),
    emergency_contact: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HealthProfileResponse:
    profile_payload = payload or _profile_payload_from_query(
        update=True,
        name=name,
        gender=gender,
        birthday=birthday,
        height_cm=height_cm,
        weight_kg=weight_kg,
        chronic_diseases=chronic_diseases,
        allergies=allergies,
        dietary_preferences=dietary_preferences,
        medication_notes=medication_notes,
        emergency_contact=emergency_contact,
    )
    return upsert_profile(db, current_user, profile_payload)


@router.delete("")
def remove_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    delete_profile(db, current_user)
    return {"message": "Profile deleted"}
