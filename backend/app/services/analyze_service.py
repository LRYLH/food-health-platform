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
from ..schemas.analyze import AnalyzeTextRequest
from .algorithm_client import AlgorithmUnavailable, analyze_food_image


SUGAR_KEYWORDS = [
    "sugar",
    "sucrose",
    "glucose",
    "fructose",
    "maltose",
    "糖",
    "蔗糖",
    "葡萄糖",
    "果糖",
    "麦芽糖",
]
SODIUM_KEYWORDS = ["sodium", "salt", "钠", "食盐", "盐"]
FAT_KEYWORDS = ["fat", "trans fat", "脂肪", "反式脂肪"]


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _json_load(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    target = Path(path)
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def _flatten_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_flatten_values(item))
        return result
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            result.extend(_flatten_values(item))
        return result
    return [str(value)]


def extract_ingredients(raw_result: dict[str, Any]) -> list[str]:
    if "ingredients" in raw_result and isinstance(raw_result["ingredients"], list):
        return [str(item).strip() for item in raw_result["ingredients"] if str(item).strip()]

    ingredients = raw_result.get("ingredients", {})
    if isinstance(ingredients, dict):
        items = ingredients.get("items", [])
    else:
        items = ingredients
    return [str(item).strip() for item in _flatten_values(items) if str(item).strip()]


def extract_nutrition(raw_result: dict[str, Any]) -> dict[str, Any]:
    nutrition = raw_result.get("nutrition_facts", raw_result.get("nutrition", {}))
    if isinstance(nutrition, dict):
        return nutrition
    return {"items": nutrition}


def extract_food_name(raw_result: dict[str, Any]) -> str | None:
    for key in ("food_name", "product_name", "name"):
        value = raw_result.get(key)
        if value:
            return str(value)
    meta = raw_result.get("meta")
    if isinstance(meta, dict) and meta.get("food_name"):
        return str(meta["food_name"])
    return None


def health_advice_for(task: ScanHistory) -> str:
    rag_result = load_rag_output(task)
    if rag_result.get("health_advice"):
        return str(rag_result["health_advice"])

    advice_parts = [part for part in [task.summary, *task.warnings, *task.suggestions] if part]
    if advice_parts:
        return " ".join(advice_parts)
    if task.status == ScanStatus.failed:
        return task.error_message or "分析任务失败。"
    return "分析尚未完成，请稍后查询。"


def risk_level_code(risk_level: RiskLevel) -> str:
    if risk_level == RiskLevel.high:
        return "HIGH"
    if risk_level == RiskLevel.medium:
        return "MEDIUM"
    return "LOW"


def _risk_from_code(code: str) -> RiskLevel:
    normalized = code.upper()
    if normalized == "HIGH":
        return RiskLevel.high
    if normalized == "MEDIUM":
        return RiskLevel.medium
    return RiskLevel.low


def _profile_contains(values: list[str], keywords: set[str]) -> bool:
    normalized_values = {value.strip().lower() for value in values if value}
    return bool(normalized_values & keywords)


def _risk_from_text(
    text: str,
    allergies: list[str],
    diseases: list[str],
) -> tuple[RiskLevel, list[str]]:
    normalized = text.lower()
    warnings: list[str] = []

    for allergen in allergies:
        if allergen and allergen.lower() in normalized:
            warnings.append(f"检测到可能的过敏原：{allergen}")

    disease_values = [disease.lower() for disease in diseases if disease]
    if _profile_contains(disease_values, {"diabetes", "糖尿病", "2型糖尿病"}):
        if any(keyword.lower() in normalized for keyword in SUGAR_KEYWORDS):
            warnings.append("该食品可能含糖，糖尿病用户需关注摄入量。")

    if _profile_contains(disease_values, {"hypertension", "高血压"}):
        if any(keyword.lower() in normalized for keyword in SODIUM_KEYWORDS):
            warnings.append("该食品可能含钠或盐，高血压用户需关注钠摄入。")

    if _profile_contains(disease_values, {"hyperlipidemia", "高血脂"}):
        if any(keyword.lower() in normalized for keyword in FAT_KEYWORDS):
            warnings.append("该食品可能含脂肪，高血脂用户需关注脂肪摄入。")

    if len(warnings) >= 2:
        return RiskLevel.high, warnings
    if warnings:
        return RiskLevel.medium, warnings
    return RiskLevel.low, warnings


def _suggestions_for_risk(risk_level: RiskLevel) -> list[str]:
    if risk_level == RiskLevel.high:
        return [
            "建议暂缓食用，确认配料表和营养成分后再决定。",
            "如与个人健康档案冲突，建议咨询医生或营养师。",
        ]
    if risk_level == RiskLevel.medium:
        return [
            "建议少量食用，并重点查看完整配料和营养成分表。",
            "优先选择低糖、低钠或不含个人过敏原的替代食品。",
        ]
    return ["当前分析未发现明显的个人健康风险。"]


def _task_paths(task_id: str, image_suffix: str | None = None) -> dict[str, Path]:
    suffix = image_suffix or ".bin"
    return {
        "vision_input": settings.vision_input_dir / f"{task_id}{suffix}",
        "vision_output": settings.vision_output_dir / f"{task_id}.json",
        "rag_output": settings.rag_output_dir / f"{task_id}.json",
    }


def _metadata(task: ScanHistory) -> dict[str, Any]:
    raw_result = task.raw_result if isinstance(task.raw_result, dict) else {}
    meta = raw_result.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    return meta


def load_rag_output(task: ScanHistory) -> dict[str, Any]:
    return _json_load(_metadata(task).get("rag_output_path"))


def _raw_result_text(task: ScanHistory, vision_result: dict[str, Any]) -> str:
    parts = [task.question or ""]
    parts.extend(_flatten_values(vision_result))
    return " ".join(part for part in parts if part)


def _build_extracted_text(task: ScanHistory, vision_result: dict[str, Any]) -> dict[str, Any]:
    meta = vision_result.get("meta", {})
    return {
        "question": task.question,
        "image_path": task.image_path,
        "vision_input_path": meta.get("vision_input_path"),
        "vision_output_path": meta.get("vision_output_path"),
        "rag_output_path": meta.get("rag_output_path"),
        "food_name": extract_food_name(vision_result),
        "ingredients": extract_ingredients(vision_result),
        "nutrition": extract_nutrition(vision_result),
        "expiration_date": vision_result.get("expiration_date"),
        "meta": meta,
    }


def build_task_result_payload(task: ScanHistory) -> dict[str, Any]:
    rag_result = load_rag_output(task)
    if rag_result:
        return {
            "food_name": rag_result.get("food_name"),
            "ingredients": rag_result.get("ingredients", []),
            "risk_level": rag_result.get("risk_level", risk_level_code(task.risk_level)),
            "health_advice": rag_result.get("health_advice", health_advice_for(task)),
            "tts_audio_url": rag_result.get("tts_audio_url"),
        }

    raw_result = task.raw_result or {}
    return {
        "food_name": extract_food_name(raw_result),
        "ingredients": extract_ingredients(raw_result),
        "risk_level": risk_level_code(task.risk_level),
        "health_advice": health_advice_for(task),
        "tts_audio_url": raw_result.get("tts_audio_url"),
    }


async def save_upload_file(file: UploadFile, user_id: int) -> str:
    settings.vision_input_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix or ".bin"
    path = settings.vision_input_dir / f"user_{user_id}_{uuid4().hex}{suffix}"
    content = await file.read()
    path.write_bytes(content)
    return str(path)


def create_scan_task(
    db: Session,
    user: User,
    question: str | None,
    image_path: str | None = None,
    structured_input: dict[str, Any] | None = None,
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

    if image_path:
        source = Path(image_path)
        paths = _task_paths(task.task_id, source.suffix)
        paths["vision_input"].parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != paths["vision_input"].resolve():
            shutil.move(str(source), paths["vision_input"])
        task.image_path = str(paths["vision_input"])
        task.raw_result = {
            **(task.raw_result or {}),
            "meta": {
                **((task.raw_result or {}).get("meta", {})),
                "vision_input_path": str(paths["vision_input"]),
                "vision_output_path": str(paths["vision_output"]),
                "rag_output_path": str(paths["rag_output"]),
            },
        }
        db.commit()
        db.refresh(task)

    return task


def _populate_algorithm_result(task: ScanHistory) -> str | None:
    if not task.image_path:
        return None

    meta = _metadata(task)
    try:
        vision_result = analyze_food_image(task.image_path)
        algorithm_error = None
    except AlgorithmUnavailable as exc:
        vision_result = dict(task.raw_result or {})
        vision_result["ingredients"] = vision_result.get("ingredients", {"items": []})
        vision_result["nutrition_facts"] = vision_result.get("nutrition_facts", {})
        vision_result["expiration_date"] = vision_result.get("expiration_date", {})
        algorithm_error = str(exc)
        meta["algorithm_error"] = algorithm_error
        meta["algorithm_fallback"] = True

    vision_result["meta"] = {
        **(vision_result.get("meta") if isinstance(vision_result.get("meta"), dict) else {}),
        **meta,
    }
    _json_dump(Path(meta["vision_output_path"]), vision_result)
    task.raw_result = vision_result
    return algorithm_error


def _build_rag_result(
    *,
    task: ScanHistory,
    vision_result: dict[str, Any],
    risk_level: RiskLevel,
) -> dict[str, Any]:
    warnings = task.warnings or []
    suggestions = _suggestions_for_risk(risk_level)
    advice_parts = [task.summary or "", *warnings, *suggestions]
    return {
        "task_id": task.task_id,
        "food_name": extract_food_name(vision_result),
        "ingredients": extract_ingredients(vision_result),
        "risk_level": risk_level_code(risk_level),
        "health_advice": " ".join(part for part in advice_parts if part),
        "tts_audio_url": vision_result.get("tts_audio_url"),
        "source": {
            "vision_output_path": _metadata(task).get("vision_output_path"),
        },
    }


def _populate_rag_result(task: ScanHistory, risk_level: RiskLevel) -> dict[str, Any]:
    meta = _metadata(task)
    vision_result = _json_load(meta.get("vision_output_path")) or (task.raw_result or {})
    rag_result = _build_rag_result(
        task=task,
        vision_result=vision_result,
        risk_level=risk_level,
    )
    _json_dump(Path(meta["rag_output_path"]), rag_result)
    return rag_result


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

        algorithm_error = _populate_algorithm_result(task)
        vision_result = _json_load(_metadata(task).get("vision_output_path")) or (task.raw_result or {})

        profile = db.scalar(
            select(HealthProfile).where(HealthProfile.user_id == task.user_id)
        )
        allergies = profile.allergies if profile else []
        diseases = profile.chronic_diseases if profile else []

        risk_level, warnings = _risk_from_text(
            _raw_result_text(task, vision_result),
            allergies,
            diseases,
        )

        task.risk_level = risk_level
        task.warnings = warnings
        task.suggestions = _suggestions_for_risk(risk_level)
        task.summary = (
            "食品包装分析完成，已结合用户健康档案生成风险提示。"
            if algorithm_error is None
            else "算法服务暂不可用，已使用本地规则完成基础风险分析。"
        )

        rag_result = _populate_rag_result(task, risk_level)
        task.risk_level = _risk_from_code(str(rag_result.get("risk_level", "LOW")))
        task.extracted_text = _build_extracted_text(task, vision_result)
        task.error_message = algorithm_error
        task.status = ScanStatus.completed
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
            "ingredients": {"items": payload.ingredients},
            "nutrition_facts": payload.nutrition,
            "source": "text",
        },
    )
