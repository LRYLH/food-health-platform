# RAG、后端主服务与视觉模型 JSON 对接规范

版本：`v1.0`

适用范围：后端 FastAPI 主服务、视觉模型服务、RAG 推理服务之间的内部数据交换。用户侧 HTTP 接口仍沿用 `POST /tasks/analyze` 和 `GET /tasks/{task_id}/status`；本文只定义模型链路内部 JSON 契约。

## 1. 数据流

```text
前端上传图片/问题
  -> FastAPI 后端创建 task_id
  -> BackendVisionRequest + 图片文件
  -> 视觉模型返回 VisionResult
  -> 后端合并用户健康档案，生成 RagAnalysisRequest
  -> RAG 返回 RagAnalysisResponse
  -> 后端落库并供 /tasks/{task_id}/status 查询
```

当前代码已经使用以下目录作为文件交接点：

- `model_io/vision_input/{task_id}.*`：待视觉模型分析的食品包装图片。
- `model_io/vision_output/{task_id}.json`：当前实现中写入的是 RAG 输入 JSON，即本文的 `RagAnalysisRequest`。
- `model_io/rag_output/{task_id}.json`：RAG 最终输出 JSON，即本文的 `RagAnalysisResponse`。

为了兼容现有实现，`model_io/vision_output/{task_id}.json` 暂不强制改名；如后续拆分更清晰，建议新增 `model_io/rag_input/{task_id}.json`。

## 2. 通用约定

- 所有 JSON 文件编码必须为 `UTF-8`。
- 时间字段使用 ISO 8601 UTC 格式，例如 `2026-05-18T08:30:00Z`。
- 枚举值使用大写英文：`LOW`、`MEDIUM`、`HIGH`、`UNKNOWN`。
- 金额、营养含量、置信度等数值字段优先使用 number；无法结构化时保留原始文本到 `raw_text`。
- 字段不存在与字段为空语义不同：未知字段可省略；已确认没有内容时用空数组、空对象或 `null`。
- 各服务必须忽略自己不认识的扩展字段，避免版本升级时互相阻塞。
- 每个顶层对象必须包含 `schema_version` 和 `task_id`。

## 3. BackendVisionRequest：后端主服务 -> 视觉模型

用途：描述一次视觉分析任务。图片本体可以通过文件路径、对象存储 URL 或二进制 RPC 传输；JSON 只承载元数据和上下文。

推荐文件：`model_io/vision_input/{task_id}.request.json`

对应 Schema：`backend/docs/schemas/backend_vision_request.schema.json`

```json
{
  "schema_version": "1.0",
  "task_id": "6f2b4c3d9f8142e6b2b0d6c9cf7d7f10",
  "created_at": "2026-05-18T08:30:00Z",
  "image": {
    "path": "model_io/vision_input/6f2b4c3d9f8142e6b2b0d6c9cf7d7f10.jpg",
    "mime_type": "image/jpeg",
    "original_filename": "package.jpg",
    "sha256": "optional-image-sha256"
  },
  "user_context": {
    "voice_query": "糖尿病可以吃这个吗？",
    "profile": {
      "allergens": ["花生"],
      "chronic_diseases": ["2型糖尿病"]
    }
  },
  "trace": {
    "request_id": "http-request-id",
    "source": "fastapi"
  }
}
```

必填字段：

- `schema_version`
- `task_id`
- `image.path`

## 4. VisionResult：视觉模型 -> 后端主服务

用途：视觉模型对食品包装图的结构化识别结果。该对象也会作为 `RagAnalysisRequest.vision` 原样传递给 RAG。

推荐文件：`model_io/vision_result/{task_id}.json`；当前代码可直接作为内存返回值，由后端合并到 `model_io/vision_output/{task_id}.json`。

对应 Schema：`backend/docs/schemas/vision_result.schema.json`

```json
{
  "schema_version": "1.0",
  "task_id": "6f2b4c3d9f8142e6b2b0d6c9cf7d7f10",
  "food_name": "夹心饼干",
  "brand": "示例品牌",
  "ingredients": {
    "raw_text": "配料：小麦粉、白砂糖、植物油、花生酱",
    "items": ["小麦粉", "白砂糖", "植物油", "花生酱"]
  },
  "nutrition_facts": {
    "raw_text": "营养成分表：能量 2050kJ 蛋白质 6.5g 脂肪 22g 碳水化合物 65g 钠 320mg",
    "serving_size": "100g",
    "items": [
      {
        "name": "能量",
        "per_100g": "2050kJ",
        "nrv": "24%"
      },
      {
        "name": "钠",
        "per_100g": "320mg",
        "nrv": "16%"
      }
    ]
  },
  "expiration_date": {
    "raw_text": "保质期：12个月",
    "value": "12个月"
  },
  "detected_claims": ["无反式脂肪酸"],
  "ocr_text_blocks": [
    {
      "text": "配料：小麦粉、白砂糖、植物油、花生酱",
      "type": "ingredients",
      "bbox": [120, 340, 860, 430],
      "confidence": 0.91
    }
  ],
  "meta": {
    "model": "baidu_ocr+deepseek",
    "ocr_engine": "baidu_ocr",
    "quality_score": 0.86,
    "elapsed_ms": 6300,
    "preprocess_steps": {
      "brightness": "normal",
      "perspective_corrected": true
    }
  }
}
```

必填字段：

- `schema_version`
- `task_id`
- `ingredients.items`
- `nutrition_facts.items`
- `meta`

字段说明：

- `food_name`：识别不到时可省略，后端展示时降级为“该食品”。
- `ingredients.items`：只放清洗后的配料名称，不放解释性文字。
- `nutrition_facts.items[].name`：建议使用中文标准名称，如“能量”“蛋白质”“脂肪”“碳水化合物”“钠”。
- `ocr_text_blocks[].bbox`：顺序为 `[x1, y1, x2, y2]`，基于原图像素坐标。
- `meta.quality_score`：建议归一化为 `0-1`；如果视觉模型仍输出旧版大数值，后端不得因此拒绝该结果。

## 5. RagAnalysisRequest：后端主服务 -> RAG

用途：后端把视觉结构化结果、用户健康档案和用户问题合并后传给 RAG。

当前文件：`model_io/vision_output/{task_id}.json`

对应 Schema：`backend/docs/schemas/rag_analysis_request.schema.json`

```json
{
  "schema_version": "1.0",
  "task_id": "6f2b4c3d9f8142e6b2b0d6c9cf7d7f10",
  "created_at": "2026-05-18T08:30:08Z",
  "voice_query": "糖尿病可以吃这个吗？",
  "user_profile": {
    "allergens": ["花生"],
    "chronic_diseases": ["2型糖尿病"],
    "dietary_preferences": [],
    "age_group": "adult"
  },
  "vision": {
    "schema_version": "1.0",
    "task_id": "6f2b4c3d9f8142e6b2b0d6c9cf7d7f10",
    "food_name": "夹心饼干",
    "ingredients": {
      "raw_text": "配料：小麦粉、白砂糖、植物油、花生酱",
      "items": ["小麦粉", "白砂糖", "植物油", "花生酱"]
    },
    "nutrition_facts": {
      "items": [
        {
          "name": "钠",
          "per_100g": "320mg",
          "nrv": "16%"
        }
      ]
    },
    "expiration_date": {
      "value": "12个月"
    },
    "meta": {
      "model": "baidu_ocr+deepseek",
      "quality_score": 0.86
    }
  },
  "retrieval": {
    "top_k": 3,
    "collections": ["food_health_standards"],
    "required_topics": ["食品安全国家标准", "糖尿病医学营养治疗指南"]
  },
  "output_requirements": {
    "language": "zh-CN",
    "risk_levels": ["LOW", "MEDIUM", "HIGH"],
    "include_citations": true,
    "answer_style": "plain"
  },
  "trace": {
    "vision_output_path": "model_io/vision_output/6f2b4c3d9f8142e6b2b0d6c9cf7d7f10.json",
    "rag_output_path": "model_io/rag_output/6f2b4c3d9f8142e6b2b0d6c9cf7d7f10.json"
  }
}
```

必填字段：

- `schema_version`
- `task_id`
- `vision`
- `user_profile`
- `voice_query`，没有用户问题时传 `null`

RAG 检索建议：

- 检索 query 不能只用用户问题；应合并 `voice_query`、`vision.food_name`、`ingredients.items`、关键营养项和用户疾病标签。
- 生成答案时必须区分“识别结果不确定”和“健康风险确定”，不能把 OCR 低置信度内容当作事实。

## 6. RagAnalysisResponse：RAG -> 后端主服务

用途：RAG 返回可落库、可展示、可追溯引用的最终分析结果。

当前文件：`model_io/rag_output/{task_id}.json`

对应 Schema：`backend/docs/schemas/rag_analysis_response.schema.json`

```json
{
  "schema_version": "1.0",
  "task_id": "6f2b4c3d9f8142e6b2b0d6c9cf7d7f10",
  "status": "completed",
  "food_name": "夹心饼干",
  "risk_level": "HIGH",
  "answer": "该食品含白砂糖和花生酱。结合用户存在2型糖尿病和花生过敏史，建议避免食用或在确认配料后谨慎选择。",
  "health_advice": "建议优先选择低糖、无花生配料且营养标签清晰的食品。",
  "warnings": [
    {
      "type": "allergen",
      "level": "HIGH",
      "message": "配料中识别到花生酱，可能触发花生过敏。"
    },
    {
      "type": "chronic_disease",
      "level": "MEDIUM",
      "message": "配料中含白砂糖，糖尿病用户需关注摄入量。"
    }
  ],
  "suggestions": ["避免食用含花生配料的同类产品", "查看营养成分表中的碳水化合物含量"],
  "reference": [
    "中国糖尿病医学营养治疗指南相关片段",
    "GB 7718 预包装食品标签通则相关片段"
  ],
  "citations": [
    {
      "source_id": "doc-gb7718-chunk-0012",
      "title": "GB 7718 预包装食品标签通则",
      "chunk": "过敏原和配料标签相关内容摘要",
      "score": 0.82
    }
  ],
  "confidence": {
    "overall": 0.78,
    "vision": 0.86,
    "retrieval": 0.81
  },
  "meta": {
    "rag_model": "qwen-max",
    "retriever": "llamaindex+milvus",
    "elapsed_ms": 4100
  }
}
```

必填字段：

- `schema_version`
- `task_id`
- `status`
- `risk_level`
- `answer`
- `reference`

兼容当前代码：

- 当前 `TaskStatusResponse` 只读取 `answer` 和 `reference`。
- `risk_level`、`warnings`、`suggestions`、`food_name` 应由后端在后续迭代中写入 `scan_history`，并扩展前端响应。
- 如果 RAG 失败，`status` 使用 `failed`，并返回 `error`：

```json
{
  "schema_version": "1.0",
  "task_id": "6f2b4c3d9f8142e6b2b0d6c9cf7d7f10",
  "status": "failed",
  "risk_level": "UNKNOWN",
  "answer": "",
  "reference": [],
  "error": {
    "code": "RAG_TIMEOUT",
    "message": "RAG service timed out"
  }
}
```

## 7. 版本升级规则

- 小版本新增可选字段，例如 `1.1`，消费者必须兼容。
- 删除字段、改变字段类型或改变必填字段时升主版本，例如 `2.0`。
- 后端主服务负责在落库前做最小校验：`task_id` 一致、必填字段存在、`risk_level` 合法、`reference` 为字符串数组。
- 视觉模型和 RAG 返回异常时，必须返回结构化 `error`，不能只返回纯文本。

