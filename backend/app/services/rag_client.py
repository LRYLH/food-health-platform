from typing import Any
from pathlib import Path
import json

import requests

from ..core.config import settings


class RagServiceError(RuntimeError):
    pass


def analyze_with_rag(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.post(
            settings.rag_service_url,
            json=payload,
            timeout=settings.rag_service_timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RagServiceError(f"RAG service request failed: {exc}") from exc

    try:
        result = response.json()
    except ValueError as exc:
        raise RagServiceError("RAG service returned non-JSON response") from exc

    if not isinstance(result, dict):
        raise RagServiceError("RAG service returned a non-object response")
    _write_rag_output_file(payload, result)
    return result


def _write_rag_output_file(payload: dict[str, Any], result: dict[str, Any]) -> None:
    vision = payload.get("vision")
    meta = vision.get("meta") if isinstance(vision, dict) else None
    if not isinstance(meta, dict) or not meta.get("rag_output_path"):
        return

    output_path = Path(str(meta["rag_output_path"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
