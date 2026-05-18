from pathlib import Path
import sys
from typing import Any

from ..core.config import settings


class AlgorithmUnavailable(RuntimeError):
    pass


def _algorithm_root() -> Path:
    if settings.algorithm_module_dir is not None:
        return settings.algorithm_module_dir.resolve()
    return Path(__file__).resolve().parents[1] / "algorithm"


def analyze_food_image(image_path: str) -> dict[str, Any]:
    if not settings.algorithm_enabled:
        raise AlgorithmUnavailable("Algorithm service is disabled by configuration")

    algorithm_root = _algorithm_root()
    if not algorithm_root.exists():
        raise AlgorithmUnavailable(f"Algorithm module directory not found: {algorithm_root}")

    root_text = str(algorithm_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    try:
        from vision_engine.pipeline import analyze
    except Exception as exc:
        raise AlgorithmUnavailable(f"Failed to load algorithm pipeline: {exc}") from exc

    try:
        result = analyze(image_path)
    except Exception as exc:
        raise AlgorithmUnavailable(f"Algorithm image analysis failed: {exc}") from exc

    if not isinstance(result, dict):
        raise AlgorithmUnavailable("Algorithm pipeline returned a non-object result")
    return result
