# Backend

FastAPI backend for the food health platform. Public routes are mounted at the
root paths defined in `../大创接口.md`.

## Requirements

- Python 3.11+
- MySQL
- Redis
- Vision and RAG dependencies when running the full model pipeline

## Auth

```http
POST /auth/wechat-login
Content-Type: application/json
```

```json
{
  "code": "wx-login-code"
}
```

Response:

```json
{
  "access_token": "jwt",
  "is_new_user": true
}
```

Use the returned token on protected endpoints:

```http
Authorization: Bearer <access_token>
```

## User APIs

```http
GET /users/me/profile
```

```json
{
  "allergens": ["seafood", "peanut"],
  "chronic_diseases": ["type 2 diabetes"]
}
```

```http
PUT /users/me/profile
Content-Type: application/json
```

```json
{
  "allergens": ["peanut"],
  "chronic_diseases": ["hypertension"]
}
```

Successful response: `null`.

```http
GET /users/me/history?page=1&size=10
```

```json
{
  "total": 1,
  "records": [
    {
      "task_id": "uuid",
      "food_name": "product name",
      "risk_level": "LOW",
      "created_at": "2026-05-17T10:00:00Z"
    }
  ]
}
```

## Task APIs

```http
POST /tasks/analyze
Content-Type: multipart/form-data
```

Fields:

- `image`: required food package image
- `voice_query`: optional user question text

Response:

```json
{
  "task_id": "uuid",
  "status": "pending"
}
```

```http
GET /tasks/{task_id}/status
```

Processing response:

```json
{
  "status": "processing"
}
```

Completed response. The `result` object is the RAG contract:

```json
{
  "status": "completed",
  "result": {
    "answer": "RAG generated answer",
    "reference": ["source chunk 1", "source chunk 2"]
  }
}
```

## Admin Knowledge APIs

```http
POST /admin/knowledge/upload
Content-Type: multipart/form-data
```

Field:

- `file`: PDF, Markdown, or another knowledge document

Response:

```json
{
  "document_id": "uuid",
  "parsed_chunks_count": 142
}
```

```http
POST /admin/knowledge/sync-vectors
Content-Type: application/json
```

```json
{
  "document_id": "uuid"
}
```

Response:

```json
{
  "status": "syncing",
  "message": "后台已开始向量化入库"
}
```

The sync endpoint stages the uploaded document into the RAG standards directory
and starts the vector indexing workflow in a background task.

## Model IO

The backend keeps model handoff files under `MODEL_IO_DIR`:

- `model_io/vision_input/{task_id}.*`: image consumed by the vision model
- `model_io/vision_output/{task_id}.json`: raw vision model JSON when the standalone vision worker writes files
- `model_io/rag_input/{task_id}.json`: RAG input JSON with `task_id`, `vision`, `user_profile`, and `voice_query`
- `model_io/rag_output/{task_id}.json`: final RAG JSON with `answer` and `reference`

Environment variables:

- `MODEL_IO_DIR=model_io`
- `KNOWLEDGE_UPLOAD_DIR=knowledge_uploads`
- `ALGORITHM_ENABLED=true`
- `ALGORITHM_MODULE_DIR=`
- `RAG_SERVICE_URL=http://algo_service:8001/api/ask`
- `RAG_SERVICE_TIMEOUT_SECONDS=120`
- `DASHSCOPE_API_KEY=`
- `LLAMA_CLOUD_API_KEY=`
