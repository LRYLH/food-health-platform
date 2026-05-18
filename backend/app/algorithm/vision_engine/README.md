# vision_engine — 食品包装图像分析模块

## 命令行入口

```bash
# 批量处理：扫描 vision_input/ 下所有图片，结果写入 vision_output/
docker exec food_health_app python app/algorithm/vision_main.py

# 处理单张图片
docker exec food_health_app python app/algorithm/vision_main.py --input /app/model_io/vision_input/abc.jpg
```

I/O 约定：

```
backend/model_io/
├── vision_input/     ← 放入待分析的食品包装图片（jpg/png/bmp/webp）
└── vision_output/    ← 每张图片对应一个 <文件名>.json 结果
```

## Python API

```python
from vision_engine.pipeline import analyze

result = analyze("path/to/package.jpg")
print(result["ingredients"]["items"])        # ["水", "食用盐", "白砂糖", ...]
print(result["nutrition_facts"]["items"])     # [{"name":"能量","per_100g":"657kJ","nrv":"8%"}, ...]
print(result["expiration_date"]["value"])     # "12个月"
```

## 环境配置

在 `backend/.env` 中配置 API 密钥（Docker 通过 `env_file` 自动注入）：

```env
BAIDU_OCR_API_KEY=你的百度OCR_API_Key
BAIDU_OCR_SECRET_KEY=你的百度OCR_Secret_Key
DEEPSEEK_API_KEY=你的DeepSeek_API_Key
```

## 流水线架构

```
vision_main.py        — 命令行入口，批量/单张处理
  └── pipeline.py     — analyze(source) 统一入口
        ├── preprocessor    — 图像预处理：CLAHE 光平衡、透视矫正、去噪锐化
        └── layout_analyzer — OCR 提取 + 结构化解析
              ├── baidu_ocr        — 百度 OCR API，图片 → 文字块
              └── deepseek_vision  — DeepSeek API，文字 → JSON
```

## analyze() 返回值

```python
{
    "image": "test_01.jpg",                        # 输入文件名
    "elapsed_s": 6.3,                              # 总耗时
    "ingredients": {
        "raw_text": "配料表：水、白砂糖...",
        "items": ["水", "白砂糖", ...]
    },
    "nutrition_facts": {
        "raw_text": "营养成分表\n能量 657kJ...",
        "items": [
            {"name": "能量", "per_100g": "657kJ", "nrv": "8%"},
            ...
        ]
    },
    "expiration_date": {
        "raw_text": "保质期：12个月",
        "value": "12个月"
    },
    "meta": {
        "ocr_engine": "baidu_ocr+deepseek",
        "quality_score": 3095.5,
        "preprocess_steps": {
            "brightness": "normal",
            "perspective_corrected": true,
            ...
        }
    }
}
```

## 容错与降级

- **OCR 引擎**：百度 OCR → EasyOCR → PaddleOCR → Tesseract，按可用性自动降级
- **文本解析**：DeepSeek API（主路径），失败自动回退正则规则解析
- **预处理**：透视矫正失败不阻断流程，继续使用原图

