# 视觉感知与推理算法模块 (Vision Perception & Reasoning)

本目录（`algorithm/`）承载了平台的核心算法逻辑，负责将原始的食品包装图像转化为可理解的结构化健康建议。模块采用了“传统视觉清洗 + 深度学习布局分析 + 大模型多模态推理”的级联架构。

## 📂 目录结构

```text
algorithm/
├── vision_engine/           # 核心算法实现包
│   ├── preprocessor.py      # 图像预处理（OpenCV）
│   ├── layout_analyzer.py   # 版面逻辑分析（LayoutLMv3）
│   └── multimodal_llm.py    # 多模态大模型封装（Qwen-VL）
├── data/
│   └── hard_samples/        # [本地新建] 存放测试原图、处理图及结果 JSON (Git 忽略)
├── models/                  # [本地新建] 存放预训练模型权重 (Git 忽略)
├── requirements.txt         # 算法模块专属依赖清单
└── rpc_server.py            # gRPC 服务端入口（对接后端网关）
```

## 🛠️ 环境配置

建议在 Python 3.10+ 虚拟环境下运行。

### 1. 安装核心依赖
由于涉及深度学习框架，建议使用国内镜像源加速：
```bash
pip install -r requirements.txt -i [https://pypi.tuna.tsinghua.edu.cn/simple](https://pypi.tuna.tsinghua.edu.cn/simple)
```

### 2. 关键依赖说明
* **OpenCV (`opencv-python-headless`)**: 执行图像去高光（CLAHE）及透视变换矫正。
* **PyTorch & Transformers**: 驱动 LayoutLMv3 与 Qwen-VL 推理。
* **Accelerate & Einops**: 优化大模型显存分配与张量计算。

## 🧠 核心组件说明

### 1. 图像预处理 (`preprocessor.py`)
- **功能**: 消除物理干扰。
- **技术**: 使用 `cv2.createCLAHE` 处理塑料袋反光，通过 Canny 边缘检测识别四点轮廓，执行 `warpPerspective` 拉正畸变图片。

### 2. 版面分析 (`layout_analyzer.py`)
- **功能**: 识别包装的空间逻辑。
- **技术**: 基于 LayoutLMv3 模型，提取“配料表”与“营养成分表”的文字及其物理坐标边界框（Bounding Box）。

### 3. 多模态推理 (`multimodal_llm.py`)
- **功能**: 生成健康报告。
- **技术**: 封装 Qwen-VL-Chat，结合 Layout 数据与 RAG 检索到的国标指南，生成具有医疗严谨性的健康风险提示。

## 🧪 本地测试流程

为确保模块接口通畅，项目根目录下提供了单点测试脚本，输出结果统一存放在 `algorithm/data/hard_samples/`。

1. **预处理测试**: `python test_preprocessor.py` —— 验证图像是否拉正及去噪。
2. **版面提取测试**: `python test_layout_analyzer.py` —— 验证是否生成结构化 JSON 数据。
3. **大模型推理测试**: `python test_multimodal_llm.py` —— 验证最终健康报告的生成逻辑。

## ⚠️ 注意事项
* **Mock 模式**: 在没有 GPU 或未下载权重时，`LayoutAnalyzer` 和 `MultimodalLLM` 可开启 `use_mock=True` 进行接口联调。
* **显存要求**: 运行完整的 Qwen-VL 推理建议至少具备 24GB 显存（如 NVIDIA 3090/4090）。
* **数据安全**: `data/hard_samples/` 下的真实照片已被 `.gitignore` 拦截，严禁上传敏感食品生产数据至公共仓库。