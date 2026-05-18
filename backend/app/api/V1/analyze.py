from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.scan_history import ScanHistory, ScanStatus
from ...models.user import User
from ...schemas.analyze import RagResultPayload, TaskStatusResponse, TaskSubmitResponse
from ...services.analyze_service import (
    build_task_result_payload,
    create_scan_task,
    run_development_analysis,
    save_upload_file,
)


router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_user_task(db: Session, current_user: User, task_id: str) -> ScanHistory:
    task = db.scalar(
        select(ScanHistory).where(
            ScanHistory.task_id == task_id,
            ScanHistory.user_id == current_user.id,
        )
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/analyze", response_model=TaskSubmitResponse)
async def submit_analysis_task(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    voice_query: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskSubmitResponse:
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")

    image_path = await save_upload_file(image, current_user.id)
    task = create_scan_task(
        db=db,
        user=current_user,
        question=voice_query,
        image_path=image_path,
    )
    background_tasks.add_task(run_development_analysis, task.task_id)
    return TaskSubmitResponse(task_id=task.task_id, status=task.status)


@router.get(
    "/{task_id}/status",
    response_model=TaskStatusResponse,
    response_model_exclude_none=True,
)
def read_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskStatusResponse:
    task = _get_user_task(db, current_user, task_id)
    if task.status != ScanStatus.completed:
        return TaskStatusResponse(status=task.status)

    result = build_task_result_payload(task)
    return TaskStatusResponse(
        status=task.status,
        result=RagResultPayload(
            answer=result["answer"],
            reference=result["reference"],
        ),
    )
