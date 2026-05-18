# rag_engine — RAG 知识增强生成模块

## 两个组件

| 文件 | 角色 | 运行方式 |
|------|------|----------|
| `indexer.py` | 离线知识库构建 | 手动执行一次 |
| `retriever.py` | 在线推理 HTTP 服务 | Docker 常驻（端口 8001） |

## 1. indexer.py — 建立知识库

将国标 PDF 文档向量化存入 Milvus。

```bash
# 把 PDF 放入 algorithm/data/standards/ 或 algorithm/data/hard_samples/
docker exec food_health_algo python app/algorithm/rag_engine/indexer.py
```

流程：PDF → BGE 向量模型 → Milvus 向量库（collection: `food_health_standards`）

## 2. retriever.py — 推理服务

已在 `docker-compose.yml` 中定义为 `algo_service` 容器，端口 8001。

### HTTP 接口

```
POST http://algo_service:8001/api/ask
Content-Type: application/json

{
  "schema_version": "1.0",
  "task_id": "6f2b4c3d9f8142e6b2b0d6c9cf7d7f10",
  "voice_query": "糖尿病可以吃这个吗？",
  "user_profile": {
    "allergens": ["花生"],
    "chronic_diseases": ["2型糖尿病"]
  },
  "vision": {
    "food_name": "夹心饼干",
    "ingredients": {
      "raw_text": "小麦粉、白砂糖、植物油、花生酱",
      "items": ["小麦粉", "白砂糖", "植物油", "花生酱"]
    },
    "nutrition_facts": {
      "items": [
        {"name": "能量", "per_100g": "2050kJ", "nrv": "24%"},
        {"name": "钠", "per_100g": "320mg", "nrv": "16%"}
      ]
    },
    "meta": {
      "quality_score": 0.86
    }
  }
}
```

### 返回

```json
{
  "schema_version": "1.0",
  "task_id": "6f2b4c3d9f8142e6b2b0d6c9cf7d7f10",
  "status": "completed",
  "food_name": "夹心饼干",
  "risk_level": "HIGH",
  "answer": "该食品含白砂糖和花生酱。结合用户存在2型糖尿病和花生过敏史，建议避免食用。",
  "health_advice": "建议优先选择低糖、无花生配料且营养标签清晰的食品。",
  "warnings": [
    {"type": "allergen", "level": "HIGH", "message": "配料中识别到花生酱，可能触发花生过敏。"}
  ],
  "suggestions": ["避免食用含花生配料的同类产品"],
  "reference": ["GB 7718 相关片段..."],
  "citations": [],
  "confidence": {
    "overall": 0.82,
    "vision": 0.86,
    "retrieval": 0.78
  },
  "meta": {
    "rag_model": "qwen-max",
    "retriever": "llamaindex+milvus"
  }
}
```

### 失败返回

```json
{
  "schema_version": "1.0",
  "task_id": "...",
  "status": "failed",
  "risk_level": "UNKNOWN",
  "answer": "",
  "reference": [],
  "error": {
    "code": "RAG_PROCESSING_ERROR",
    "message": "..."
  }
}
```

## 调用链路

```
后端 FastAPI (8000)
  → POST http://algo_service:8001/api/ask
  → retriever: Milvus 检索 top-3 国标
  → Qwen-Max 推理生成
  → 返回分析结果
```

## 前置条件

- Milvus 已启动且已通过 `indexer.py` 注入数据
- `.env` 中配置了 `DASHSCOPE_API_KEY`
