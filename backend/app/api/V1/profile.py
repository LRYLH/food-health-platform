from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.health_profile import HealthProfile
from ...models.scan_history import ScanHistory
from ...models.user import User
from ...schemas.analyze import HistoryRecord, HistoryResponse
from ...schemas.profile import HealthProfileCreate, UserProfilePayload, UserProfileResponse
from ...services.analyze_service import build_task_result_payload, risk_level_code
from ...services.profile_service import upsert_profile


router = APIRouter(prefix="/users/me", tags=["users"])


@router.get("/profile", response_model=UserProfileResponse)
def read_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    profile = db.scalar(select(HealthProfile).where(HealthProfile.user_id == current_user.id))
    if profile is None:
        return UserProfileResponse(allergens=[], chronic_diseases=[])
    return UserProfileResponse(
        allergens=profile.allergies or [],
        chronic_diseases=profile.chronic_diseases or [],
    )


@router.put("/profile", response_model=None)
def replace_profile(
    payload: UserProfilePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    upsert_profile(
        db,
        current_user,
        HealthProfileCreate(
            allergies=payload.allergens,
            chronic_diseases=payload.chronic_diseases,
        ),
    )
    return None


@router.get("/history", response_model=HistoryResponse)
def read_history(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HistoryResponse:
    total = db.scalar(
        select(func.count())
        .select_from(ScanHistory)
        .where(ScanHistory.user_id == current_user.id)
    ) or 0
    statement = (
        select(ScanHistory)
        .where(ScanHistory.user_id == current_user.id)
        .order_by(desc(ScanHistory.created_at))
        .offset((page - 1) * size)
        .limit(size)
    )
    records = []
    for task in db.scalars(statement).all():
        result = build_task_result_payload(task)
        records.append(
            HistoryRecord(
                task_id=task.task_id,
                food_name=result.get("food_name"),
                risk_level=result.get("risk_level", risk_level_code(task.risk_level)),
                created_at=task.created_at,
            )
        )
    return HistoryResponse(total=total, records=records)
