"""
模块名称: vision_engine.preprocessor
功能描述: 图像预处理与物理干扰消除模块 (系统“抗干扰先锋”)

本模块主要处理来自前端的真实超市场景“随手拍”图像（可能存在反光、褶皱、倾斜畸变等问题）。
通过传统的计算机视觉技术，将低质量的物理世界图像转化为干净、平整、机器可读的标准化矩阵。

核心算法与技术栈:
    1. 自适应直方图均衡化 (CLAHE): 使用 `cv2.createCLAHE` 压暗局部高光、提亮阴影，
        消除塑料包装袋上的刺眼反光与白斑。
    2. 边缘检测与轮廓提取: 识别包装袋或营养成分表所在的核心矩形区域。
    3. 透视变换矫正: 计算变换矩阵并执行 `cv2.warpPerspective`，将带有空间透视畸变的
        “歪斜”包装强行拉平拉正。

输入参数:
    - image (numpy.ndarray): 原始的 RGB 像素矩阵（通常带有环境噪声）。

返回结果:
    - processed_image (numpy.ndarray): 去噪、展平后的标准化图片矩阵，直接供下游
        layout_analyzer 进行版面分析。
"""

import cv2
import numpy as np

class ImagePreprocessor:
    def __init__(self, clip_limit=2.0, tile_grid_size=(8, 8)):
        # 初始化 CLAHE 算法实例，设定对比度阈值和切片网格大小
        self.clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)

    def process(self, image: np.ndarray) -> np.ndarray:
        """
        执行完整的图像清洗流水线
        """
        # 第一步：处理高光反光 (CLAHE)
        enhanced_image = self._apply_clahe(image)
        
        # 第二步 & 第三步：提取轮廓并执行透视变换
        processed_image = self._correct_perspective(enhanced_image)
        
        return processed_image

    def _apply_clahe(self, image: np.ndarray) -> np.ndarray:
        """
        解决包装袋的高光和局部阴影
        """
        # 将 RGB 转换到 LAB 颜色空间，以分离亮度 (L) 与色彩 (A, B)
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        
        # 仅对亮度通道应用自适应直方图均衡化，避免色彩失真
        cl = self.clahe.apply(l_channel)
        
        # 合并通道并转换回 RGB
        merged_lab = cv2.merge((cl, a_channel, b_channel))
        enhanced_rgb = cv2.cvtColor(merged_lab, cv2.COLOR_LAB2RGB)
        
        return enhanced_rgb

    def _correct_perspective(self, image: np.ndarray) -> np.ndarray:
        """
        检测包装边缘并拉平透视畸变
        """
        # 转换为灰度图进行边缘检测计算
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # 高斯滤波降低噪点干扰
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Canny 边缘检测
        edged = cv2.Canny(blurred, 50, 150)

        # 寻找轮廓
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return image  # 未找到任何轮廓时，回退并返回原图

        # 按轮廓面积降序排序，取最大的前 5 个
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        target_contour = None

        for c in contours:
            # 获取轮廓周长
            peri = cv2.arcLength(c, True)
            # 进行多边形拟合，逼近真实形状
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)

            # 如果拟合结果包含 4 个顶点，则认定为我们要寻找的包装袋/标签矩形
            if len(approx) == 4:
                target_contour = approx
                break

        if target_contour is None:
            # 没找到规则的四边形，说明可能形变严重或没有清晰边界，返回原图
            return image

        # 拿到 4 个顶点坐标后，执行最终的透视拉平
        warped = self._four_point_transform(image, target_contour.reshape(4, 2))
        return warped

    def _four_point_transform(self, image: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """
        核心的透视变换数学计算部分
        """
        # 对四个顶点进行规范化排序（左上、右上、右下、左下）
        rect = self._order_points(pts)
        (tl, tr, br, bl) = rect

        # 计算新图像的宽度 (取顶部和底部宽度的最大值)
        width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        max_width = max(int(width_a), int(width_b))

        # 计算新图像的高度 (取左侧和右侧高度的最大值)
        height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        max_height = max(int(height_a), int(height_b))

        # 构建标准的正向俯视矩形坐标点
        dst = np.array([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1]
        ], dtype="float32")

        # 求解透视变换矩阵 (3x3)
        matrix = cv2.getPerspectiveTransform(rect, dst)
        
        # 应用矩阵，将歪曲的部分“拽”平
        warped = cv2.warpPerspective(image, matrix, (max_width, max_height))

        return warped

    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """
        将无序的四个点按顺时针排序：[左上, 右上, 右下, 左下]
        """
        rect = np.zeros((4, 2), dtype="float32")
        
        # 左上的点 (x+y) 和最小，右下的点 (x+y) 和最大
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]

        # 右上的点 (y-x) 差最小，左下的点 (y-x) 差最大
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]

        return rect