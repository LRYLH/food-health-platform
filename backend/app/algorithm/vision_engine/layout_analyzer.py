"""
视觉版面分析与文字提取模块

流程: 图片 → OCR 文字提取 → DeepSeek 文本解析(主) / 传统规则解析(回退) → 结构化 JSON
"""

import logging
import re
from typing import List, Optional, Tuple

import numpy as np

try:
    from .baidu_ocr import BaiduOCR
    from .deepseek_vision import parse_ocr_text as deepseek_parse
except ImportError:
    import sys
    from pathlib import Path

    algorithm_root = Path(__file__).resolve().parents[1]
    if str(algorithm_root) not in sys.path:
        sys.path.insert(0, str(algorithm_root))

    from vision_engine.baidu_ocr import BaiduOCR
    from vision_engine.deepseek_vision import parse_ocr_text as deepseek_parse

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 关键词定义
# ═══════════════════════════════════════════════════════════════════════════

INGREDIENT_KEYS = ["配料表", "配料", "原料", "原料表", "食料"]

NUTRITION_KEYS = ["营养成分表", "营养", "营养素"]

EXPIRATION_KEYS = [
    "保质期", "到期日", "有效期至", "生产日期", "有效期",
    "最佳食用日期", "到期日期",
]

SECTION_BREAK_KEYS = INGREDIENT_KEYS + NUTRITION_KEYS + EXPIRATION_KEYS + [
    "产品名称", "食品名称", "产品类别", "产品标准", "委托方",
    "生产许可证", "贮存条件", "食用方法", "温馨提示", "致敏",
    "过敏原", "联系方式", "生产商", "地址",
]


# ═══════════════════════════════════════════════════════════════════════════
# OCR 引擎层（优先级: Baidu OCR > EasyOCR > PaddleOCR > Tesseract）
# ═══════════════════════════════════════════════════════════════════════════

class _OCREngine:
    def __init__(self):
        self._engine = None
        self._engine_name = None

    @property
    def engine_name(self) -> str:
        if self._engine_name is None:
            self._ensure_engine()
        return self._engine_name or "unavailable"

    def _ensure_engine(self):
        if self._engine is not None:
            return

        # 1) 百度 OCR
        baidu = BaiduOCR()
        if baidu.available:
            self._engine = baidu
            self._engine_name = "baidu_ocr"
            logger.info("OCR 引擎: Baidu OCR 已就绪")
            return

        # 2) EasyOCR
        try:
            import easyocr
            gpu = __import__("torch").cuda.is_available()
            self._engine = easyocr.Reader(["ch_sim", "en"], gpu=gpu)
            self._engine_name = "easyocr"
            logger.info("OCR 引擎: EasyOCR 已就绪")
            return
        except ImportError:
            pass

        # 3) PaddleOCR
        try:
            from paddleocr import PaddleOCR
            self._engine = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False)
            self._engine_name = "paddleocr"
            logger.info("OCR 引擎: PaddleOCR 已就绪")
            return
        except Exception:
            pass

        # 4) Tesseract
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self._engine = pytesseract
            self._engine_name = "tesseract"
            logger.info("OCR 引擎: Tesseract 已就绪")
            return
        except ImportError:
            pass

        raise RuntimeError("未找到可用 OCR 引擎")

    def extract(self, image: np.ndarray) -> List[dict]:
        """提取文本块，返回 [{"text","box","confidence"}, ...]"""
        self._ensure_engine()

        if self._engine_name == "baidu_ocr":
            return self._engine.extract(image)
        elif self._engine_name == "easyocr":
            return [{"text": item[1], "box": item[0], "confidence": float(item[2])}
                    for item in self._engine.readtext(image)]
        elif self._engine_name == "paddleocr":
            raw = self._engine.ocr(image, cls=True)
            if raw is None or raw[0] is None:
                return []
            return [{"text": line[1][0], "box": line[0], "confidence": float(line[1][1])}
                    for line in raw[0]]
        elif self._engine_name == "tesseract":
            import pytesseract
            data = pytesseract.image_to_data(image, lang="chi_sim+eng", output_type=pytesseract.Output.DICT)
            results = []
            for i in range(len(data["text"])):
                t = data["text"][i].strip()
                if not t:
                    continue
                x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                conf = int(data["conf"][i]) / 100.0 if data["conf"][i] != "-1" else 0.5
                results.append({"text": t, "box": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]], "confidence": conf})
            return results
        return []


_ocr = _OCREngine()


# ═══════════════════════════════════════════════════════════════════════════
# 坐标工具
# ═══════════════════════════════════════════════════════════════════════════

def _bbox_center(box) -> Tuple[float, float]:
    xs, ys = [p[0] for p in box], [p[1] for p in box]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def _bbox_height(box) -> float:
    ys = [p[1] for p in box]
    return max(ys) - min(ys)


# ═══════════════════════════════════════════════════════════════════════════
# 板块分类与篇章聚合（回退路径用）
# ═══════════════════════════════════════════════════════════════════════════

def _classify_block(text: str) -> str:
    t = text.strip()
    if any(k in t for k in NUTRITION_KEYS):
        return "nutrition"
    if any(k in t for k in INGREDIENT_KEYS):
        return "ingredients"
    if any(k in t for k in EXPIRATION_KEYS):
        return "expiration"
    return "other"


def _extract_section_text(blocks: List[dict], header_label: str) -> Optional[str]:
    """从 OCR 块中提取指定标签区域的完整文本。"""
    keys_map = {
        "ingredients": INGREDIENT_KEYS,
        "nutrition": NUTRITION_KEYS,
        "expiration": EXPIRATION_KEYS,
    }
    keys = keys_map.get(header_label, [])

    # 找标题块
    header_idx = None
    for i, b in enumerate(blocks):
        if b.get("label") == header_label or any(k in b["text"] for k in keys):
            header_idx = i
            break

    if header_idx is None:
        return None

    header = blocks[header_idx]
    _, hy = _bbox_center(header["box"])
    avg_h = _bbox_height(header["box"]) or 15

    body_texts = [header["text"]]
    nutrition_hint = 0
    for i in range(header_idx + 1, len(blocks)):
        b = blocks[i]
        _, by = _bbox_center(b["box"])
        t = b["text"].strip()

        if by < hy - 5:
            continue

        # 遇到其他版块标题 → 停止
        if b.get("label") not in ("other", header_label):
            break
        if any(k in t for k in SECTION_BREAK_KEYS) and b.get("label") == "other":
            if _bbox_height(b["box"]) > avg_h * 1.3:
                break

        # 配料区遇到营养表特征 → 停止
        if header_label == "ingredients":
            if re.search(r"(NRV|每\s*\d+\s*克|kJ|千焦|毫克|mg|蛋白质\b|脂肪\b|碳水|能量\b)", t, re.IGNORECASE):
                nutrition_hint += 1
                if nutrition_hint >= 2:
                    break
                continue
            nutrition_hint = 0

        body_texts.append(t)
        avg_h = (avg_h + (_bbox_height(b["box"]) or avg_h)) / 2

    return "\n".join(body_texts)


# ═══════════════════════════════════════════════════════════════════════════
# 配料拆分（回退路径用，基础版）
# ═══════════════════════════════════════════════════════════════════════════

def _split_ingredients(raw: str) -> List[str]:
    if not raw:
        return []

    text = raw.replace("\r", "").replace("\n", "、")

    for kw in ["配料:", "配料：", "配料表:", "配料表：", "原料:", "原料：", "食料:", "食料：", "配料", "原料", "食料"]:
        pos = text.find(kw)
        if pos != -1:
            text = text[pos + len(kw):]
            break

    # 剥离尾部非配料字段
    text = re.sub(r"@\S*", "", text)
    text = re.sub(r"(产品|执行)标准[^:：]{0,4}[:：].*", "", text)
    text = re.sub(r"食物?(致敏|过敏)[原物质]*[:：].*", "", text)
    text = re.sub(r"(食用方法|贮存条件|产地|委托|受委托|生产商|地址|邮编|联系|服务)[:：].*", "", text)

    parts = re.split(r"[，,、;；。.、\s]+", text)
    result = [p.strip().rstrip("。.，，);)").lstrip("(（") for p in parts if p.strip()]
    result = [p for p in result if len(p) >= 1
              and not re.match(r"^[\d.%\s]+$", p)
              and not re.match(r"^[a-zA-Z0-9/]+$", p)]

    return result


# ═══════════════════════════════════════════════════════════════════════════
# 保质期提取
# ═══════════════════════════════════════════════════════════════════════════

def _parse_expiration(raw: Optional[str]) -> dict:
    if not raw:
        return {"raw_text": None, "value": None}

    fuzzy = raw
    for wrong_char in ["冰", "贮", "呆", "保", "堡"]:
        fuzzy = fuzzy.replace(wrong_char + "质期", "保质期")
    for wrong in ["个阴", "个日", "个同", "个明"]:
        fuzzy = fuzzy.replace(wrong, "个月")
    fuzzy = re.sub(r"(\d+)\s*阴\b", r"\1个月", fuzzy)
    fuzzy = re.sub(r"(\d+)\s*日\b", r"\1个月", fuzzy)

    patterns = [
        r"保质期[:：]\s*(\d+\s*[个]?\s*[月天年日])",
        r"保质期.*?[:：]\s*(见[处封口包装喷码袋瓶盖罐].{0,6})",
        r"保质期.*?(见[处封口包装喷码袋瓶盖罐].{0,6})",
        r"有效期[:：]\s*(\S+)",
        r"到期日[:：期]\s*(\S+)",
        r"生产日期.*?保质期.*?[:：]?\s*(\d+\s*[个]?\s*[月天年日])",
        r"生产日期.*?保质期.*?(见[处封口包装喷码袋瓶盖罐].{0,6})",
        r"(\d+\s*个?\s*[月天年日])",
    ]
    for pat in patterns:
        m = re.search(pat, fuzzy)
        if m:
            return {"raw_text": raw.strip(), "value": m.group(1).strip()}

    return {"raw_text": raw.strip(), "value": None}


# ═══════════════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════════════

def analyze_image_layout(image: np.ndarray) -> dict:
    """从预处理后的图片中提取结构化食品包装信息。

    优先使用 DeepSeek 解析 OCR 文本，失败则回退传统规则方法。

    Returns:
        {"ingredients": {"raw_text", "items"}, "nutrition_facts": {"raw_text", "items"},
         "expiration_date": {"raw_text", "value"}, "meta": {"ocr_engine", "text_blocks_count"}}
    """
    # 1. OCR
    text_blocks = _ocr.extract(image)
    if not text_blocks:
        logger.warning("OCR 未检测到任何文字")
        return {
            "ingredients": {"raw_text": None, "items": []},
            "nutrition_facts": {"raw_text": None, "items": []},
            "expiration_date": {"raw_text": None, "value": None},
            "meta": {"ocr_engine": _ocr.engine_name, "text_blocks_count": 0},
            "_raw_text_blocks": [],
        }

    # 2. 分类并排序
    for b in text_blocks:
        b["label"] = _classify_block(b["text"])
    text_blocks.sort(key=lambda b: (_bbox_center(b["box"])[1], _bbox_center(b["box"])[0]))

    # 3. 区域提取
    ingredients_raw = _extract_section_text(text_blocks, "ingredients")
    nutrition_raw = _extract_section_text(text_blocks, "nutrition")
    expiration_raw = _extract_section_text(text_blocks, "expiration")
    all_text = "\n".join(b["text"] for b in text_blocks)

    # ── DeepSeek 文本解析（主路径）──
    try:
        ds = deepseek_parse(all_text)
        if ds and ds.get("ingredients"):
            logger.info("版面分析: DeepSeek 文本解析")
            return {
                "food_name": ds.get("food_name"),
                "brand": ds.get("brand"),
                "ingredients": {"raw_text": ingredients_raw, "items": ds.get("ingredients") or []},
                "nutrition_facts": {"raw_text": nutrition_raw, "serving_size": ds.get("serving_size"), "items": ds.get("nutrition") or []},
                "expiration_date": {"raw_text": expiration_raw, "value": ds.get("expiration")},
                "detected_claims": ds.get("detected_claims") or [],
                "meta": {"ocr_engine": "baidu_ocr+deepseek", "text_blocks_count": len(text_blocks)},
                "_raw_text_blocks": text_blocks,
            }
    except Exception as e:
        logger.warning("DeepSeek 文本解析失败，回退传统方法: %s", e)

    # ── 传统规则解析（回退路径）──
    # 兜底：全文扫描关键词
    if not ingredients_raw:
        for kw in INGREDIENT_KEYS:
            if kw in all_text:
                pos = all_text.find(kw)
                ingredients_raw = all_text[pos:pos + 300]
                break
    if not nutrition_raw:
        for kw in NUTRITION_KEYS:
            if kw in all_text:
                pos = all_text.find(kw)
                nutrition_raw = all_text[pos:pos + 500]
                break
    if not expiration_raw:
        for kw in EXPIRATION_KEYS:
            if kw in all_text:
                pos = all_text.find(kw)
                snippet = all_text[pos:pos + 80]
                end = snippet.find("\n")
                expiration_raw = snippet[:end] if end > 0 else snippet
                break

    return {
        "ingredients": {"raw_text": ingredients_raw, "items": _split_ingredients(ingredients_raw) if ingredients_raw else []},
        "nutrition_facts": {"raw_text": nutrition_raw, "items": []},
        "expiration_date": _parse_expiration(expiration_raw),
        "meta": {"ocr_engine": _ocr.engine_name, "text_blocks_count": len(text_blocks)},
        "_raw_text_blocks": text_blocks,
    }
