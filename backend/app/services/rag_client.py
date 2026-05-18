from typing import Any

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
    return result

