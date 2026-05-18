# algorithm — 算法模块总览

## 整体流水线

```
用户上传图片 + 问题
        │
        ▼
┌─ vision_engine ───────────────────────────────────────┐
│  vision_main.py          命令行入口（批量/单张）         │
│    └── pipeline.py       analyze() 统一入口             │
│          ├── preprocessor    图像预处理（CLAHE/矫正）     │
│          └── layout_analyzer OCR + 结构化解析            │
│                ├── baidu_ocr        百度 OCR → 文字块    │
│                └── deepseek_vision  DeepSeek → JSON      │
│                                                          │
│  输入: model_io/vision_input/{task_id}.request.json      │
│  输出: model_io/vision_output/{task_id}.json (VisionResult)│
└──────────────────────────────────────────────────────────┘
        │ 后端读取 VisionResult，合并用户健康档案
        ▼
┌─ rag_engine ──────────────────────────────────────────┐
│  indexer.py              离线建库（一次性）              │
│  retriever.py            HTTP 服务（端口 8001）          │
│                                                          │
│  输入: model_io/rag_input/{task_id}.json (RagAnalysisRequest)│
│  输出: model_io/rag_output/{task_id}.json (RagAnalysisResponse)│
└──────────────────────────────────────────────────────────┘
        │
        ▼
    前端展示结果
```

## 目录结构

```
algorithm/
├── vision_main.py                # 视觉模块命令行入口
├── vision_engine/                # 食品包装图像分析
│   ├── pipeline.py               #   对外统一入口 analyze()
│   ├── preprocessor.py           #   图像预处理
│   ├── layout_analyzer.py        #   OCR 引擎调度 + 文本解析
│   ├── baidu_ocr.py              #   百度 OCR API
│   └── deepseek_vision.py        #   DeepSeek 文本解析
└── rag_engine/                   # RAG 知识增强生成
    ├── indexer.py                #   知识库构建（离线）
    └── retriever.py              #   推理服务（在线 HTTP）
```

## 两种调用方式

### 方式一：后端直接调 Python API（当前使用）

```python
# algorithm_client.py 做的事
from vision_engine.pipeline import analyze
result = analyze("/path/to/image.jpg")
# → VisionResult dict
```

### 方式二：命令行独立运行

```bash
docker exec food_health_app python app/algorithm/vision_main.py
docker exec food_health_app python app/algorithm/vision_main.py --task-id <task_id>
```

## 容错机制

- **OCR 降级**：百度 OCR → EasyOCR → PaddleOCR → Tesseract
- **解析降级**：DeepSeek API（主） → 传统正则规则（回退）
- **预处理降级**：透视矫正失败继续用原图，不阻断流程
