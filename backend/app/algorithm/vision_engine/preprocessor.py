"""
模块名称: vision_engine.preprocessor
功能描述: 图像预处理与物理干扰消除模块 (系统"抗干扰先锋")

本模块主要处理来自前端的真实超市场景"随手拍"图像（可能存在反光、褶皱、倾斜畸变等问题）。
通过传统的计算机视觉技术，将低质量的物理世界图像转化为干净、平整、机器可读的标准化矩阵。

核心算法与技术栈:
    1. 自适应直方图均衡化 (CLAHE): 使用 `cv2.createCLAHE` 压暗局部高光、提亮阴影，
       消除塑料包装袋上的刺眼反光与白斑。
    2. 边缘检测与轮廓提取: 识别包装袋或营养成分表所在的核心矩形区域。
    3. 透视变换矫正: 计算变换矩阵并执行 `cv2.warpPerspective`，将带有空间透视畸变的
       "歪斜"包装强行拉平拉正。

输入参数:
    - source (numpy.ndarray | str): 原始的 RGB 像素矩阵或图片文件路径。

返回结果:
    - dict: {"image": np.ndarray, "quality_score": float, "steps": dict}
"""

import cv2
import numpy as np
from typing import Tuple, Optional


def _estimate_sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _auto_orient(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    if w > h * 1.5:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    return image


def _estimate_brightness(gray: np.ndarray) -> float:
    return float(gray.mean())


def apply_clahe(
    image: np.ndarray,
    clip_limit: float = 2.0,
    tile_grid_size: Tuple[int, int] = (8, 8),
) -> np.ndarray:
    """在 LAB 色彩空间对 L 通道做 CLAHE，压高光、提阴影。"""
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    cl = clahe.apply(l)
    merged = cv2.merge((cl, a, b))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)


def _find_largest_quad(contours) -> Optional[np.ndarray]:
    quads = []
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quads.append(approx)
    if not quads:
        return None
    quads.sort(key=cv2.contourArea, reverse=True)
    return quads[0]


def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _compute_output_size(rect: np.ndarray, max_dim: int = 2000) -> Tuple[int, int]:
    tl, tr, br, bl = rect
    w = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    h = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        w, h = int(w * scale), int(h * scale)
    return max(w, 1), max(h, 1)


def correct_perspective(image: np.ndarray) -> Tuple[np.ndarray, bool]:
    """检测包装边缘并拉平透视畸变。

    若检测到的四边形面积不足原图 10%，或矫正后尺寸过小（<300px），
    则跳过矫正，避免对货架全景等非单品图做错误裁剪。
    """
    h_orig, w_orig = image.shape[:2]
    original_area = h_orig * w_orig

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    candidates = []
    for low_t in (30, 50, 80):
        edged = cv2.Canny(blurred, low_t, low_t * 3)
        dilated = cv2.dilate(edged, None, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        quad = _find_largest_quad(contours)
        if quad is not None:
            candidates.append(quad)

    if not candidates:
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 8
        )
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        quad = _find_largest_quad(contours)
        if quad is not None:
            candidates.append(quad)

    if not candidates:
        return image, False

    best = max(candidates, key=cv2.contourArea)

    # 面积不足原图 20% → 跳过矫正（避免裁掉配料/保质期等边缘信息）
    if cv2.contourArea(best) < original_area * 0.20:
        return image, False

    pts = best.reshape(4, 2).astype("float32")
    rect = _order_points(pts)

    w, h = _compute_output_size(rect)

    # 矫正后尺寸不足 300px → 跳过
    if w < 300 or h < 300:
        return image, False

    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype="float32")
    matrix = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, matrix, (w, h))
    return warped, True


def _sharpen(image: np.ndarray, strength: float = 0.5) -> np.ndarray:
    blurred = cv2.GaussianBlur(image, (0, 0), 3)
    return cv2.addWeighted(image, 1.0 + strength, blurred, -strength, 0)


def _denoise(image: np.ndarray, strength: int = 5) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)


def load_image(source) -> np.ndarray:
    """统一加载入口：支持文件路径或 numpy 数组。"""
    if isinstance(source, np.ndarray):
        return source
    if isinstance(source, str):
        img = cv2.imread(source)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {source}")
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    raise TypeError(f"不支持的输入类型: {type(source)}")


def run_image_pipeline(source, **kwargs) -> dict:
    """对外统一入口：一键执行完整清洗流水线。

    Args:
        source: 图片路径 (str) 或 RGB numpy 数组。
        clip_limit: CLAHE 裁剪限幅，默认根据亮度自适应。
        tile_grid_size: CLAHE 分块大小，默认 (8, 8)。
        sharpen_strength: 锐化强度，默认 0.4。
        denoise_strength: 去噪强度，默认 5。

    Returns:
        dict: {
            "image": np.ndarray (矫正后的 RGB 图像),
            "quality_score": float (清晰度评分),
            "steps": dict (各步骤执行情况),
        }
    """
    img = load_image(source)
    input_shape = img.shape
    steps = {}

    # 1. 自动旋转
    img = _auto_orient(img)
    steps["oriented"] = img.shape != input_shape

    # 2. 评估亮度以自适应 CLAHE 强度
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    brightness = _estimate_brightness(gray)

    # 暗图增强 CLAHE，亮图减弱
    if brightness < 100:
        clip_limit = kwargs.get("clip_limit", 4.0)
        tile_grid_size = kwargs.get("tile_grid_size", (4, 4))
        steps["brightness"] = "dark"
    elif brightness > 200:
        clip_limit = kwargs.get("clip_limit", 1.5)
        tile_grid_size = kwargs.get("tile_grid_size", (8, 8))
        steps["brightness"] = "bright"
    else:
        clip_limit = kwargs.get("clip_limit", 2.0)
        tile_grid_size = kwargs.get("tile_grid_size", (8, 8))
        steps["brightness"] = "normal"

    # 3. 去噪
    img = _denoise(img, strength=kwargs.get("denoise_strength", 5))
    steps["denoised"] = True

    # 4. CLAHE 光平衡
    img = apply_clahe(img, clip_limit=clip_limit, tile_grid_size=tile_grid_size)
    steps["clahe_applied"] = True

    # 5. 透视矫正
    img, corrected = correct_perspective(img)
    steps["perspective_corrected"] = corrected

    # 6. 锐化
    sharpen_s = kwargs.get("sharpen_strength", 0.5 if brightness < 100 else 0.4)
    img = _sharpen(img, strength=sharpen_s)
    steps["sharpened"] = True

    # 7. 尺寸限制（大图缩放到 2000px，加速 OCR 且提高精度）
    h, w = img.shape[:2]
    max_side = max(h, w)
    if max_side > 2000:
        scale = 2000 / max_side
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        steps["resized"] = True
    else:
        steps["resized"] = False

    # 8. 质量评估
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    quality = _estimate_sharpness(gray)

    return {"image": img, "quality_score": round(quality, 1), "steps": steps}
