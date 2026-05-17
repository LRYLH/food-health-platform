from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import SessionLocal
from ..models.health_profile import HealthProfile
from ..models.scan_history import RiskLevel, ScanHistory, ScanStatus
from ..models.user import User
from ..schemas.analyze import AnalyzeTextRequest


def _risk_from_text(text: str, allergies: list[str], diseases: list[str]) -> tuple[RiskLevel, list[str]]:
    normalized = text.lower()
    warnings: list[str] = []

    for allergen in allergies:
        if allergen and allergen.lower() in normalized:
            warnings.append(f"Detected possible allergen: {allergen}")

    diabetes_keywords = ["sugar", "sucrose", "glucose", "fructose", "糖", "蔗糖", "葡萄糖"]
    if any(disease in {"diabetes", "糖尿病"} for disease in diseases):
        if any(keyword in normalized for keyword in diabetes_keywords):
            warnings.append("The product may contain sugars that need attention for diabetes.")

    hypertension_keywords = ["sodium", "salt", "钠", "盐"]
    if any(disease in {"hypertension", "高血压"} for disease in diseases):
        if any(keyword in normalized for keyword in hypertension_keywords):
            warnings.append("The product may contain sodium/salt that needs attention for hypertension.")

    if len(warnings) >= 2:
        return RiskLevel.high, warnings
    if warnings:
        return RiskLevel.medium, warnings
    return RiskLevel.low, warnings


def _suggestions_for_risk(risk_level: RiskLevel) -> list[str]:
    if risk_level == RiskLevel.high:
        return [
            "Avoid eating before confirming the ingredient list.",
            "Consult a doctor or dietitian if this conflicts with your health profile.",
        ]
    if risk_level == RiskLevel.medium:
        return [
            "Eat cautiously and check the full ingredient and nutrition labels.",
            "Prefer lower sugar, lower sodium, or allergen-free alternatives when available.",
        ]
    return ["No obvious personal risk was detected in the current development analysis."]


async def save_upload_file(file: UploadFile, user_id: int) -> str:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix or ".bin"
    path = settings.upload_dir / f"user_{user_id}_{uuid4().hex}{suffix}"
    content = await file.read()
    path.write_bytes(content)
    return str(path)


def create_scan_task(
    db: Session,
    user: User,
    question: str | None,
    image_path: str | None = None,
    structured_input: dict | None = None,
) -> ScanHistory:
    task = ScanHistory(
        task_id=uuid4().hex,
        user_id=user.id,
        image_path=image_path,
        question=question,
        status=ScanStatus.pending,
        raw_result=structured_input or {},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def run_development_analysis(task_id: str) -> None:
    db = SessionLocal()
    try:
        task = db.scalar(select(ScanHistory).where(ScanHistory.task_id == task_id))
        if task is None:
            return

        task.status = ScanStatus.processing
        db.commit()

        profile = db.scalar(
            select(HealthProfile).where(HealthProfile.user_id == task.user_id)
        )
        allergies = profile.allergies if profile else []
        diseases = profile.chronic_diseases if profile else []

        raw_text_parts = [task.question or ""]
        raw_text_parts.extend(task.raw_result.get("ingredients", []))
        raw_text_parts.extend(str(value) for value in task.raw_result.get("nutrition", {}).values())
        raw_text = " ".join(raw_text_parts)
        risk_level, warnings = _risk_from_text(raw_text, allergies, diseases)

        task.status = ScanStatus.completed
        task.risk_level = risk_level
        task.warnings = warnings
        task.suggestions = _suggestions_for_risk(risk_level)
        task.summary = (
            "Development analysis completed. This result is rule-based and should be "
            "replaced by the algorithm service before production use."
        )
        task.extracted_text = {
            "question": task.question,
            "image_path": task.image_path,
            "structured_input": task.raw_result,
        }
        db.commit()
    except Exception as exc:
        task = db.scalar(select(ScanHistory).where(ScanHistory.task_id == task_id))
        if task is not None:
            task.status = ScanStatus.failed
            task.error_message = str(exc)
            db.commit()
    finally:
        db.close()


def create_text_scan_task(
    db: Session,
    user: User,
    payload: AnalyzeTextRequest,
) -> ScanHistory:
    return create_scan_task(
        db=db,
        user=user,
        question=payload.question,
        structured_input={
            "product_name": payload.product_name,
            "ingredients": payload.ingredients,
            "nutrition": payload.nutrition,
        },
    )
