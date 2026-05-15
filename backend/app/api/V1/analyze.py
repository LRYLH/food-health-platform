import json

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.scan_history import ScanHistory
from ...models.user import User
from ...schemas.analyze import (
    AnalyzeResultResponse,
    AnalyzeResultRequest,
    AnalyzeSubmitResponse,
    AnalyzeTextRequest,
    ScanHistoryItem,
)
from ...services.analyze_service import (
    create_scan_task,
    create_text_scan_task,
    run_development_analysis,
    save_upload_file,
)


router = APIRouter(prefix="/analyze", tags=["analyze"])


def _normalize_query_list(values: list[str] | None) -> list[str]:
    if values is None:
        return []
    normalized: list[str] = []
    for value in values:
        normalized.extend(item.strip() for item in value.split(",") if item.strip())
    return normalized


def _nutrition_from_query(nutrition: str | None) -> dict[str, str | float | int]:
    if not nutrition:
        return {}
    try:
        parsed = json.loads(nutrition)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="nutrition must be a JSON object string",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="nutrition must be a JSON object string",
        )
    return parsed


def _get_user_task(db: Session, current_user: User, task_id: str) -> ScanHistory:
    task = db.scalar(
        select(ScanHistory).where(
            ScanHistory.task_id == task_id,
            ScanHistory.user_id == current_user.id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Analysis task not found")
    return task


@router.post("/image", response_model=AnalyzeSubmitResponse, status_code=202)
async def submit_image_analysis(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    question: str | None = Form(default=None),
    question_query: str | None = Query(default=None, alias="question"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyzeSubmitResponse:
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")

    image_path = await save_upload_file(image, current_user.id)
    task = create_scan_task(
        db=db,
        user=current_user,
        question=question or question_query,
        image_path=image_path,
    )
    background_tasks.add_task(run_development_analysis, task.task_id)
    return AnalyzeSubmitResponse(
        task_id=task.task_id,
        status=task.status,
        message="Analysis task accepted",
    )


@router.post("/text", response_model=AnalyzeSubmitResponse, status_code=202)
def submit_text_analysis(
    background_tasks: BackgroundTasks,
    payload: AnalyzeTextRequest | None = Body(default=None),
    product_name: str | None = Query(default=None, max_length=128),
    ingredients: list[str] | None = Query(default=None),
    nutrition: str | None = Query(default=None),
    question: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyzeSubmitResponse:
    text_payload = payload or AnalyzeTextRequest(
        product_name=product_name,
        ingredients=_normalize_query_list(ingredients),
        nutrition=_nutrition_from_query(nutrition),
        question=question,
    )
    task = create_text_scan_task(db, current_user, text_payload)
    background_tasks.add_task(run_development_analysis, task.task_id)
    return AnalyzeSubmitResponse(
        task_id=task.task_id,
        status=task.status,
        message="Analysis task accepted",
    )


@router.api_route(
    "/result",
    methods=["GET", "POST"],
    response_model=AnalyzeResultResponse,
)
def get_analysis_result_by_query_or_body(
    payload: AnalyzeResultRequest | None = Body(default=None),
    task_id: str | None = Query(default=None, min_length=1, max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyzeResultResponse:
    target_task_id = task_id or (payload.task_id if payload else None)
    if target_task_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="task_id is required",
        )
    return _get_user_task(db, current_user, target_task_id)


@router.get("/{task_id}", response_model=AnalyzeResultResponse)
def get_analysis_result(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyzeResultResponse:
    return _get_user_task(db, current_user, task_id)


@router.get("", response_model=list[ScanHistoryItem])
def list_analysis_history(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ScanHistory]:
    statement = (
        select(ScanHistory)
        .where(ScanHistory.user_id == current_user.id)
        .order_by(desc(ScanHistory.created_at))
        .offset(offset)
        .limit(min(limit, 100))
    )
    return list(db.scalars(statement).all())
