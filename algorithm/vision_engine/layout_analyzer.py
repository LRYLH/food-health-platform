"""
模块名称: vision_engine.layout_analyzer
功能描述: 视觉版面分析与空间逻辑提取模块

本模块承接图像预处理的输出，核心任务是理解食品包装上人类的“排版逻辑”。
传统的 OCR 仅能提取乱序文本，而本模块通过多模态模型，不仅识别文字，还能识别文字
在物理空间上的位置关系，从而精准切分出不同维度的信息块。

核心算法与技术栈:
    1. 预训练模型: 加载 LayoutLMv3 模型权重。
    2. 多模态融合推理: 结合视觉特征（图像）、文本特征（字面意思）和空间特征（坐标），
        进行联合推理。
    3. 目标检测与分类: 提取文字的边界框坐标（Bounding Box），并判断该区域的具体属性
        （例如：明确区分“配料表”区域与“营养成分表”区域）。

输入参数:
    - processed_image (numpy.ndarray): 经过 preprocessor 清洗后的标准化图片矩阵。

返回结果:
    - layout_data (dict/JSON): 包含文本内容、对应边界框坐标以及分类标签的结构化 JSON 数据。
"""

import json
import numpy as np
from PIL import Image

# 尝试导入深度学习库，做异常捕获方便本地轻量化测试
try:
    import torch
    from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

class LayoutAnalyzer:
    def __init__(self, model_path="microsoft/layoutlmv3-base", use_mock=False):
        """
        初始化版面分析器
        :param model_path: HuggingFace 模型路径或本地权重文件夹路径
        :param use_mock: 是否使用模拟数据返回（用于本地没有 GPU 时的接口联调）
        """
        self.use_mock = use_mock
        self.device = "cuda" if torch.cuda.is_available() else "cpu" if HAS_TORCH else "cpu"
        
        if not self.use_mock and HAS_TORCH:
            print(f"正在加载 LayoutLMv3 模型到 {self.device}...")
            # apply_ocr=True 会调用系统底层的 Tesseract OCR
            self.processor = LayoutLMv3Processor.from_pretrained(model_path, apply_ocr=True)
            self.model = LayoutLMv3ForTokenClassification.from_pretrained(model_path).to(self.device)
            # 假设你在微调时定义了这些标签，这里做个映射字典
            self.id2label = self.model.config.id2label 
        elif not self.use_mock and not HAS_TORCH:
            print("警告: 未检测到 PyTorch 或 Transformers 库，将强制降级为 Mock 模式。")
            self.use_mock = True

    def analyze(self, image_matrix: np.ndarray) -> dict:
        """
        执行版面分析并提取结构化 JSON
        """
        if self.use_mock:
            return self._mock_inference()

        # 将 OpenCV 的 numpy 矩阵转为 PIL 图像
        image = Image.fromarray(image_matrix)

        # 1. 处理器处理：图像 -> Tensor + OCR 预提取
        encoding = self.processor(image, return_tensors="pt")
        # 将数据推送到对应的设备 (GPU/CPU)
        for k, v in encoding.items():
            encoding[k] = v.to(self.device)

        # 2. 模型前向推理
        with torch.no_grad():
            outputs = self.model(**encoding)

        # 3. 解析预测结果
        logits = outputs.logits
        predictions = logits.argmax(-1).squeeze().tolist()
        token_boxes = encoding.bbox.squeeze().tolist()
        
        # 将 tokenizer 切碎的 token 还原为单词/句子（这里简化了聚合逻辑）
        # 实际项目中，你需要根据 token 的 B-label 和 I-label 拼接完整的字符串
        structured_data = self._format_predictions(predictions, token_boxes, self.processor.tokenizer.convert_ids_to_tokens(encoding.input_ids.squeeze().tolist()))

        return structured_data

    def _format_predictions(self, predictions, boxes, tokens) -> dict:
        """
        将模型输出的零散 token 聚合为结构化的业务 JSON
        """
        result = {
            "配料表": {"text": "", "box": []},
            "营养成分": {"text": "", "box": []},
            "其他": []
        }
        
        # 遍历预测结果并分类（演示逻辑，需根据你微调 LayoutLMv3 的实际 Label 调整）
        for pred, box, token in zip(predictions, boxes, tokens):
            label = self.id2label.get(pred, "O")
            if token in ["[CLS]", "[SEP]", "[PAD]"]:
                continue
                
            clean_token = token.replace("Ġ", "").replace(" ", "")
            
            if "LABEL_INGREDIENT" in label: # 假设这是配料表的标签名
                result["配料表"]["text"] += clean_token
                # 简单粗暴地扩大外接矩形框
                if not result["配料表"]["box"]:
                    result["配料表"]["box"] = box
                else:
                    result["配料表"]["box"] = [
                        min(result["配料表"]["box"][0], box[0]),
                        min(result["配料表"]["box"][1], box[1]),
                        max(result["配料表"]["box"][2], box[2]),
                        max(result["配料表"]["box"][3], box[3])
                    ]
            elif "LABEL_NUTRITION" in label:
                result["营养成分"]["text"] += clean_token
                # ... 坐标聚合逻辑同上
        return result

    def _mock_inference(self) -> dict:
        """返回假数据，用于前后端或流水线前期的快速打通"""
        return {
            "配料表": {
                "text": "水，白砂糖，果葡糖浆，全脂乳粉，食品添加剂(甜蜜素，柠檬酸)",
                "box": [100, 200, 400, 350]
            },
            "营养成分": {
                "text": "能量: 200kJ, 蛋白质: 1.5g, 脂肪: 0g, 碳水化合物: 10g",
                "box": [100, 400, 400, 800]
            }
        }