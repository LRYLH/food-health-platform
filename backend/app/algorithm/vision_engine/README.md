# vision_engine — 食品包装图像分析模块

## 快速开始

```python
from vision_engine.pipeline import analyze

result = analyze("path/to/package.jpg")
print(result["ingredients"]["items"])        # ["水", "食用盐", "白砂糖", ...]
print(result["nutrition_facts"]["items"])     # [{"name":"能量","per_100g":"657kJ","nrv":"8%"}, ...]
print(result["expiration_date"]["value"])     # "12个月"
```

## 环境配置

在 `backend/.env` 中配置 API 密钥（Docker 通过 `env_file` 自动注入，本地开发时手动创建）：

```env
BAIDU_OCR_API_KEY=你的百度OCR_API_Key
BAIDU_OCR_SECRET_KEY=你的百度OCR_Secret_Key
DEEPSEEK_API_KEY=你的DeepSeek_API_Key
```

## 流水线架构

```
pipeline.py           — 对外唯一入口 analyze(source)
  ├── preprocessor    — 图像预处理：CLAHE 光平衡、透视矫正、去噪锐化、大图缩放
  └── layout_analyzer — OCR 提取 + 结构化解析
        ├── baidu_ocr        — 百度 OCR API，图片 → 文字块
        └── deepseek_vision  — DeepSeek API，文字 → JSON
```

## analyze() 返回值

```python
{
    "ingredients": {
        "raw_text": "配料表：水、白砂糖...",       # OCR 提取的配料区原文
        "items": ["水", "白砂糖", ...]            # 拆分后的配料列表
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
        "value": "12个月"                          # 可能是"见封口处"等描述性文字
    },
    "meta": {
        "ocr_engine": "baidu_ocr+deepseek",        # 实际使用的引擎组合
        "quality_score": 3095.5,                   # 预处理后图像清晰度评分
        "preprocess_steps": {                      # 预处理各步骤执行情况
            "brightness": "normal",
            "perspective_corrected": true,
            ...
        }
    }
}
```

## 容错与降级

- **OCR 引擎**：百度 OCR → EasyOCR → PaddleOCR → Tesseract，按可用性自动降级
- **文本解析**：DeepSeek API（主路径），失败自动回退传统正则规则解析
- **预处理**：透视矫正失败不阻断流程，直接使用原图继续

## 预处理说明

预处理步骤对 OCR 准确率有正向提升（实测 +11% 文字检出率）：

1. 自动旋转（横图转竖）
2. 自适应 CLAHE 光平衡（暗图增亮、亮图压光）
3. 透视矫正（斜拍包装拉平）
4. 去噪 + 锐化
5. 大图等比缩放至 2000px（加速 OCR 且提高精度）
