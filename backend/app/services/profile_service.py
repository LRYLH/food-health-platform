from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.health_profile import HealthProfile
from ..models.user import User
from ..schemas.profile import HealthProfileCreate, HealthProfileUpdate


def get_profile(db: Session, user: User) -> HealthProfile:
    profile = db.scalar(select(HealthProfile).where(HealthProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Health profile not found",
        )
    return profile


def upsert_profile(
    db: Session,
    user: User,
    payload: HealthProfileCreate | HealthProfileUpdate,
) -> HealthProfile:
    profile = db.scalar(select(HealthProfile).where(HealthProfile.user_id == user.id))
    data = payload.model_dump(exclude_unset=True)
    if profile is None:
        profile = HealthProfile(user_id=user.id, **data)
        db.add(profile)
    else:
        for key, value in data.items():
            setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile


def delete_profile(db: Session, user: User) -> None:
    profile = db.scalar(select(HealthProfile).where(HealthProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Health profile not found",
        )
    db.delete(profile)
    db.commit()
