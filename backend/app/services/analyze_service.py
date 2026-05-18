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


SUGAR_KEYWORDS = ["sugar", "sucrose", "glucose", "fructose", "糖", "蔗糖", "葡萄糖", "果糖"]
SODIUM_KEYWORDS = ["sodium", "salt", "钠", "食盐", "盐"]
FAT_KEYWORDS = ["fat", "trans fat", "脂肪", "反式脂肪"]


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
    return "LOW"


def _profile_has(values: list[str], keywords: set[str]) -> bool:
    normalized = {value.strip().lower() for value in values if value}
    return bool(normalized & keywords)


def _risk_from_text(text: str, user_profile: dict[str, list[str]]) -> tuple[RiskLevel, list[str]]:
    normalized = text.lower()
    warnings: list[str] = []

    for allergen in user_profile["allergens"]:
        if allergen and allergen.lower() in normalized:
            warnings.append(f"检测到可能的过敏原：{allergen}")

    disease_values = [disease.lower() for disease in user_profile["chronic_diseases"] if disease]
    if _profile_has(disease_values, {"diabetes", "糖尿病", "2型糖尿病"}):
        if any(keyword.lower() in normalized for keyword in SUGAR_KEYWORDS):
            warnings.append("该食品可能含糖，糖尿病用户需关注摄入量。")

    if _profile_has(disease_values, {"hypertension", "高血压"}):
        if any(keyword.lower() in normalized for keyword in SODIUM_KEYWORDS):
            warnings.append("该食品可能含钠或盐，高血压用户需关注钠摄入。")

    if _profile_has(disease_values, {"hyperlipidemia", "高血脂"}):
        if any(keyword.lower() in normalized for keyword in FAT_KEYWORDS):
            warnings.append("该食品可能含脂肪，高血脂用户需关注脂肪摄入。")

    if len(warnings) >= 2:
        return RiskLevel.high, warnings
    if warnings:
        return RiskLevel.medium, warnings
    return RiskLevel.low, warnings


def _risk_suggestion(risk_level: RiskLevel) -> str:
    if risk_level == RiskLevel.high:
        return "建议暂缓食用，确认配料表和营养成分后再决定。"
    if risk_level == RiskLevel.medium:
        return "建议少量食用，并重点查看完整配料和营养成分表。"
    return "当前分析未发现明显的个人健康风险。"


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

    task.image_path = str(paths["vision_input"])
    task.raw_result = {
        "meta": {
            "vision_input_path": str(paths["vision_input"]),
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


def _fallback_rag_payload(
    *,
    rag_input: dict[str, Any],
    risk_level: RiskLevel,
    warnings: list[str],
) -> dict[str, Any]:
    food_name = extract_food_name(rag_input) or "该食品"
    ingredients = extract_ingredients(rag_input)
    ingredients_text = "、".join(ingredients) if ingredients else "暂未识别到明确配料"
    warning_text = " ".join(warnings) if warnings else _risk_suggestion(risk_level)
    answer = (
        f"{food_name}的识别配料包括：{ingredients_text}。"
        f"综合用户健康档案，风险等级为{risk_level_code(risk_level)}。{warning_text}"
    )
    return {
        "answer": answer,
        "reference": ["rag_input", *warnings],
    }


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

        risk_level, warnings = _risk_from_text(
            " ".join([task.question or "", *_flatten(rag_input)]),
            user_profile,
        )
        rag_output = _fallback_rag_payload(
            rag_input=rag_input,
            risk_level=risk_level,
            warnings=warnings,
        )
        _write_json(Path(_metadata(task)["rag_output_path"]), rag_output)

        task.status = ScanStatus.completed
        task.risk_level = risk_level
        task.warnings = warnings
        task.suggestions = [_risk_suggestion(risk_level)]
        task.summary = rag_output["answer"]
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
