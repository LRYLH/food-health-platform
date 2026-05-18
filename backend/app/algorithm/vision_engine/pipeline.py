"""
食品包装图像分析 — 唯一对外入口

用法:
    from vision_engine.pipeline import analyze

    result = analyze("path/to/image.jpg")
    # → {"ingredients": {...}, "nutrition_facts": {...}, "expiration_date": {...}, "meta": {...}}
"""

from vision_engine.preprocessor import run_image_pipeline
from vision_engine.layout_analyzer import analyze_image_layout


def analyze(source) -> dict:
    """分析食品包装图像，提取配料、营养成分、保质期信息。

    Args:
        source: 图片文件路径 (str) 或 RGB numpy 数组 (np.ndarray)。

    Returns:
        {
            "ingredients": {
                "items": ["配料1", "配料2", ...]
            },
            "nutrition_facts": {
                "items": [{"name": "能量", "per_100g": "657kJ", "nrv": "8%"}, ...]
            },
            "expiration_date": {
                "value": "12个月"
            },
            "meta": {
                "ocr_engine": "baidu_ocr+deepseek",
                "quality_score": 3095.5,
                "preprocess_steps": {"brightness": "normal", "perspective_corrected": true, ...}
            }
        }
    """
    # 1. 图像预处理
    prep = run_image_pipeline(source)

    # 2. OCR + 版面解析
    layout = analyze_image_layout(prep["image"])

    # 3. 合并元信息
    layout["meta"]["quality_score"] = prep["quality_score"]
    layout["meta"]["preprocess_steps"] = prep["steps"]

    return layout
