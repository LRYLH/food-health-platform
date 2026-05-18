# Backend

FastAPI backend for the food health platform. The public API follows
`../大创接口.md` and is mounted at root-level paths.

## Requirements

- Python 3.11
- MySQL
- Redis
- Algorithm dependencies when full image OCR and vision analysis are required

Docs:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`

## Authentication

Login returns a JWT access token and also sets auth cookies for clients that
prefer cookie-based requests.

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

Authenticated requests should send:

```http
Authorization: Bearer <access_token>
```

## Main APIs

### Health Profile

```http
GET /users/me/profile
```

Response:

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

Successful response is `null`.

### Analyze Task

```http
POST /tasks/analyze
Content-Type: multipart/form-data
```

Fields:

- `image`: required food package image file
- `voice_query`: optional text converted from the user's voice query

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

Completed response:

```json
{
  "status": "completed",
  "result": {
    "food_name": "product name",
    "ingredients": ["wheat flour", "sugar"],
    "risk_level": "HIGH",
    "health_advice": "advice text",
    "tts_audio_url": null
  }
}
```

`risk_level` values are `LOW`, `MEDIUM`, and `HIGH`.

### History

```http
GET /users/me/history?page=1&size=10
```

Response:

```json
{
  "total": 128,
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

## Algorithm Integration

`POST /tasks/analyze` calls the local algorithm module through
`backend/app/algorithm/vision_engine/pipeline.py` by default.

Model file flow:

- `backend/model_io/vision_input/{task_id}.*`: image file consumed by the vision model
- `backend/model_io/vision_output/{task_id}.json`: raw vision model JSON output
- `backend/model_io/rag_output/{task_id}.json`: final RAG-stage JSON returned by task status APIs

Relevant environment variables:

- `ALGORITHM_ENABLED=false`: disables algorithm execution and uses local rule fallback
- `ALGORITHM_MODULE_DIR=/path/to/algorithm`: overrides the default algorithm path
- `MODEL_IO_DIR=model_io`: controls where the three model IO folders live
- `RESPONSE_ENVELOPE_ENABLED=false`: keeps responses in the raw format required by `大创接口.md`

When the algorithm dependencies are unavailable, tasks still complete with the
local rule-based fallback and record the algorithm error in the task metadata.
