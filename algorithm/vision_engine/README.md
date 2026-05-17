# vision_engine — 食品包装图像分析模块

## 快速开始

```python
from vision_engine.pipeline import analyze

result = analyze("path/to/package.jpg")
print(result["ingredients"]["items"])       # ["水", "食用盐", "白砂糖", ...]
print(result["nutrition_facts"]["items"])    # [{"name":"能量","per_100g":"657kJ","nrv":"8%"}, ...]
print(result["expiration_date"]["value"])    # "12个月"
```

## 环境配置

在 `algorithm/.env` 中配置 API 密钥：

```env
BAIDU_OCR_API_KEY=你的百度OCR_API_Key
BAIDU_OCR_SECRET_KEY=你的百度OCR_Secret_Key
DEEPSEEK_API_KEY=你的DeepSeek_API_Key
```

- 百度 OCR：用于从图片中提取文字。需在[百度智能云控制台](https://console.bce.baidu.com) → 文字识别 → 应用列表 创建应用并开通"通用文字识别（高精度含位置版）"
- DeepSeek：用于将 OCR 文本解析为结构化 JSON。需在 [DeepSeek 开放平台](https://platform.deepseek.com) 获取 API Key

## analyze() 返回值

```python
{
    "ingredients": {
        "items": ["配料1", "配料2", ...]           # 配料列表
    },
    "nutrition_facts": {
        "items": [
            {
                "name": "能量",                     # 营养素名称
                "per_100g": "657kJ",                # 每100克含量
                "nrv": "8%"                         # 营养素参考值
            },
            ...
        ]
    },
    "expiration_date": {
        "value": "12个月"                           # 保质期，可能是"见封口处"等文字
    },
    "meta": {
        "ocr_engine": "baidu_ocr+deepseek",         # 使用的引擎
        "quality_score": 3095.5,                    # 图片清晰度评分
        "preprocess_steps": {                       # 预处理步骤执行情况
            "brightness": "normal",
            "perspective_corrected": true,
            ...
        }
    }
}
```

## 内部架构

```
pipeline.py (入口)
  ├── preprocessor.py    图像预处理：CLAHE光平衡、透视矫正、去噪锐化
  └── layout_analyzer.py 文字提取与解析
        ├── baidu_ocr.py       百度 OCR API，提取图片文字
        └── deepseek_vision.py DeepSeek API，将文字解析为结构化 JSON
```

主路径：百度 OCR 提取文字 → DeepSeek 解析为 JSON。如果 DeepSeek 不可用，自动回退到传统规则解析。

## 预处理说明

预处理对百度 OCR 有益（实测 +11% 文字检出率），步骤包括：
1. 自动旋转（横图转竖）
2. 自适应 CLAHE 光平衡（暗图增亮、亮图压光）
3. 透视矫正（拉平斜拍包装）
4. 去噪 + 锐化
5. 大图等比缩放（限制 2000px，加速 OCR）
