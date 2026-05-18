"""
食品包装图像分析 — 对外唯一入口

主路径: Baidu OCR → DeepSeek 文本解析
回退路径: Baidu OCR → 传统规则解析
"""
import logging
import time

import numpy as np

from .preprocessor import run_image_pipeline

logger = logging.getLogger(__name__)


def analyze(source, task_id: str = "") -> dict:
    """分析食品包装图像，返回 VisionResult 格式（符合 docs/model_io_json_contract.md）。

    Args:
        source: 图片文件路径 (str) 或 RGB numpy 数组 (np.ndarray)。
        task_id: 任务 ID，用于结果追溯。

    Returns:
        VisionResult schema:
        {
            "schema_version": "1.0",
            "task_id": "...",
            "food_name": "...",
            "brand": "...",
            "ingredients": {"raw_text": "...", "items": [...]},
            "nutrition_facts": {"raw_text": "...", "serving_size": "...", "items": [...]},
            "expiration_date": {"raw_text": "...", "value": "..."},
            "detected_claims": [...],
            "ocr_text_blocks": [...],
            "meta": {"model": "...", "ocr_engine": "...", "quality_score": 0.0,
                     "elapsed_ms": 0, "preprocess_steps": {...}}
        }
    """
    from .layout_analyzer import analyze_image_layout

    t0 = time.perf_counter()

    # 1. 图像预处理
    prep = run_image_pipeline(source)
    image = prep["image"]

    # 2. Baidu OCR + DeepSeek 文本解析（主路径）
    layout = analyze_image_layout(image)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    nf = layout.get("nutrition_facts", {})
    meta = layout.get("meta", {})

    return {
        "schema_version": "1.0",
        "task_id": task_id,
        "food_name": layout.get("food_name"),
        "brand": layout.get("brand"),
        "ingredients": layout.get("ingredients", {"raw_text": None, "items": []}),
        "nutrition_facts": {
            "raw_text": nf.get("raw_text"),
            "serving_size": nf.get("serving_size"),
            "items": nf.get("items") or [],
        },
        "expiration_date": layout.get("expiration_date", {"raw_text": None, "value": None}),
        "detected_claims": layout.get("detected_claims") or [],
        "ocr_text_blocks": _build_ocr_blocks(layout.pop("_raw_text_blocks", [])),
        "meta": {
            "model": "baidu_ocr+deepseek",
            "ocr_engine": meta.get("ocr_engine", "baidu_ocr"),
            "quality_score": _normalize_quality(prep["quality_score"]),
            "elapsed_ms": elapsed_ms,
            "preprocess_steps": prep["steps"],
        },
    }


def _normalize_quality(raw_score: float) -> float:
    """将 Laplacian 方差归一化到 0-1 区间。"""
    return round(min(1.0, raw_score / 2000.0), 3)


def _build_ocr_blocks(raw_blocks: list) -> list:
    """将 OCR 块转换为契约格式 [x1, y1, x2, y2]。"""
    result = []
    for b in raw_blocks:
        box = b.get("box", [])
        if box and len(box) == 4:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            bbox = [min(xs), min(ys), max(xs), max(ys)]
        else:
            bbox = [0, 0, 0, 0]
        result.append({
            "text": b.get("text", ""),
            "type": b.get("label", "other"),
            "bbox": bbox,
            "confidence": b.get("confidence", 0.0),
        })
    return result
