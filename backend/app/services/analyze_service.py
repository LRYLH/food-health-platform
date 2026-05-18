from pathlib import Path
import json
import shutil
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import SessionLocal
from ..models.health_profile import HealthProfile
from ..models.scan_history import RiskLevel, ScanHistory, ScanStatus
from ..models.user import User
from .algorithm_client import AlgorithmUnavailable, analyze_food_image
from .rag_client import RagServiceError, analyze_with_rag


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    target = Path(path)
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def _flatten(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_flatten(item))
        return result
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            result.extend(_flatten(item))
        return result
    return [str(value)]


def _task_paths(task_id: str, suffix: str = ".bin") -> dict[str, Path]:
    return {
        "vision_input": settings.vision_input_dir / f"{task_id}{suffix}",
        "vision_request": settings.vision_input_dir / f"{task_id}.request.json",
        "vision_output": settings.vision_output_dir / f"{task_id}.json",
        "rag_input": settings.rag_input_dir / f"{task_id}.json",
        "rag_output": settings.rag_output_dir / f"{task_id}.json",
    }


def _metadata(task: ScanHistory) -> dict[str, Any]:
    raw_result = task.raw_result if isinstance(task.raw_result, dict) else {}
    meta = raw_result.get("meta")
    if isinstance(meta, dict):
        return meta
    vision = raw_result.get("vision")
    if isinstance(vision, dict):
        vision_meta = vision.get("meta")
        if isinstance(vision_meta, dict):
            return vision_meta
    return {}


def _profile_payload(profile: HealthProfile | None) -> dict[str, list[str]]:
    if profile is None:
        return {"allergens": [], "chronic_diseases": []}
    return {
        "allergens": profile.allergies or [],
        "chronic_diseases": profile.chronic_diseases or [],
    }


def _vision_payload(rag_input: dict[str, Any]) -> dict[str, Any]:
    vision = rag_input.get("vision")
    if isinstance(vision, dict):
        return vision
    return rag_input


def extract_ingredients(payload: dict[str, Any]) -> list[str]:
    vision = _vision_payload(payload)
    ingredients = vision.get("ingredients", {})
    if isinstance(ingredients, dict):
        ingredients = ingredients.get("items", [])
    return [item.strip() for item in _flatten(ingredients) if item.strip()]


def extract_food_name(payload: dict[str, Any]) -> str | None:
    vision = _vision_payload(payload)
    for key in ("food_name", "product_name", "name"):
        value = vision.get(key)
        if value:
            return str(value)
    meta = vision.get("meta")
    if isinstance(meta, dict) and meta.get("food_name"):
        return str(meta["food_name"])
    return None


def risk_level_code(risk_level: RiskLevel) -> str:
    if risk_level == RiskLevel.high:
        return "HIGH"
    if risk_level == RiskLevel.medium:
        return "MEDIUM"
    if risk_level == RiskLevel.unknown:
        return "UNKNOWN"
    return "LOW"


def _risk_level_from_code(value: Any) -> RiskLevel:
    normalized = str(value or "").strip().lower()
    if normalized == "high":
        return RiskLevel.high
    if normalized == "medium":
        return RiskLevel.medium
    if normalized == "low":
        return RiskLevel.low
    return RiskLevel.unknown


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _warning_messages(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    messages: list[str] = []
    for item in value:
        if isinstance(item, dict):
            message = item.get("message")
            if message:
                messages.append(str(message))
        elif item is not None:
            messages.append(str(item))
    return messages


def load_vision_output(task: ScanHistory) -> dict[str, Any]:
    return _read_json(_metadata(task).get("vision_output_path"))


def load_rag_input(task: ScanHistory) -> dict[str, Any]:
    meta = _metadata(task)
    return _read_json(meta.get("rag_input_path")) or _read_json(meta.get("vision_output_path"))


def load_rag_output(task: ScanHistory) -> dict[str, Any]:
    payload = _read_json(_metadata(task).get("rag_output_path"))
    if not payload:
        return {}
    return {
        "answer": str(payload.get("answer", "")),
        "reference": [str(item) for item in payload.get("reference", [])],
    }


def build_task_result_payload(task: ScanHistory) -> dict[str, Any]:
    return load_rag_output(task) or {"answer": "", "reference": []}


async def save_upload_file(file: UploadFile, user_id: int) -> str:
    settings.vision_input_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix or ".bin"
    path = settings.vision_input_dir / f"user_{user_id}_{uuid4().hex}{suffix}"
    path.write_bytes(await file.read())
    return str(path)


def create_scan_task(
    db: Session,
    user: User,
    question: str | None,
    image_path: str,
) -> ScanHistory:
    task = ScanHistory(
        task_id=uuid4().hex,
        user_id=user.id,
        image_path=image_path,
        question=question,
        status=ScanStatus.pending,
        raw_result={},
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    source = Path(image_path)
    paths = _task_paths(task.task_id, source.suffix)
    paths["vision_input"].parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != paths["vision_input"].resolve():
        shutil.move(str(source), paths["vision_input"])

    profile = db.scalar(select(HealthProfile).where(HealthProfile.user_id == user.id))
    vision_request = {
        "schema_version": "1.0",
        "task_id": task.task_id,
        "image": {
            "path": str(paths["vision_input"]),
            "mime_type": None,
            "original_filename": Path(image_path).name,
        },
        "user_context": {
            "voice_query": question,
            "profile": _profile_payload(profile),
        },
        "trace": {
            "source": "fastapi",
        },
    }
    _write_json(paths["vision_request"], vision_request)

    task.image_path = str(paths["vision_input"])
    task.raw_result = {
        "meta": {
            "vision_input_path": str(paths["vision_input"]),
            "vision_request_path": str(paths["vision_request"]),
            "vision_output_path": str(paths["vision_output"]),
            "rag_input_path": str(paths["rag_input"]),
            "rag_output_path": str(paths["rag_output"]),
        }
    }
    db.commit()
    db.refresh(task)
    return task


def _run_vision(task: ScanHistory) -> tuple[dict[str, Any], str | None]:
    try:
        return analyze_food_image(task.image_path or ""), None
    except AlgorithmUnavailable as exc:
        return {
            "ingredients": {"items": []},
            "nutrition_facts": {},
            "expiration_date": {},
        }, str(exc)


def _build_rag_input(
    *,
    task: ScanHistory,
    vision_result: dict[str, Any],
    user_profile: dict[str, list[str]],
    algorithm_error: str | None,
) -> dict[str, Any]:
    meta = {**_metadata(task)}
    meta.setdefault("rag_input_path", str(settings.rag_input_dir / f"{task.task_id}.json"))
    meta.setdefault("rag_output_path", str(settings.rag_output_dir / f"{task.task_id}.json"))
    vision_meta = vision_result.get("meta") if isinstance(vision_result.get("meta"), dict) else {}
    return {
        "schema_version": "1.0",
        "task_id": task.task_id,
        "vision": {
            **vision_result,
            "meta": {
                **vision_meta,
                **meta,
                **({"algorithm_error": algorithm_error} if algorithm_error else {}),
            },
        },
        "user_profile": user_profile,
        "voice_query": task.question,
    }


def _raise_for_failed_rag(rag_output: dict[str, Any]) -> None:
    if rag_output.get("status") != "failed":
        return
    error = rag_output.get("error")
    if isinstance(error, dict):
        message = error.get("message") or error.get("code") or "RAG service returned failed status"
        raise RagServiceError(str(message))
    raise RagServiceError("RAG service returned failed status")


def run_development_analysis(task_id: str) -> None:
    db = SessionLocal()
    task: ScanHistory | None = None
    try:
        task = db.scalar(select(ScanHistory).where(ScanHistory.task_id == task_id))
        if task is None:
            return

        task.status = ScanStatus.processing
        task.error_message = None
        db.commit()

        profile = db.scalar(select(HealthProfile).where(HealthProfile.user_id == task.user_id))
        user_profile = _profile_payload(profile)
        vision_result, algorithm_error = _run_vision(task)
        rag_input = _build_rag_input(
            task=task,
            vision_result=vision_result,
            user_profile=user_profile,
            algorithm_error=algorithm_error,
        )
        _write_json(Path(rag_input["vision"]["meta"]["rag_input_path"]), rag_input)
        task.raw_result = rag_input

        rag_output = analyze_with_rag(rag_input)
        _write_json(Path(_metadata(task)["rag_output_path"]), rag_output)
        _raise_for_failed_rag(rag_output)

        suggestions = _string_list(rag_output.get("suggestions"))
        health_advice = rag_output.get("health_advice")
        if not suggestions and health_advice:
            suggestions = [str(health_advice)]

        task.status = ScanStatus.completed
        task.risk_level = _risk_level_from_code(rag_output.get("risk_level"))
        task.warnings = _warning_messages(rag_output.get("warnings"))
        task.suggestions = suggestions
        task.summary = str(rag_output.get("answer", ""))
        task.extracted_text = {
            "food_name": extract_food_name(rag_input),
            "ingredients": extract_ingredients(rag_input),
        }
        task.error_message = algorithm_error
        db.commit()
    except Exception as exc:
        if task is None:
            task = db.scalar(select(ScanHistory).where(ScanHistory.task_id == task_id))
        if task is not None:
            task.status = ScanStatus.failed
            task.error_message = str(exc)
            db.commit()
    finally:
        db.close()
