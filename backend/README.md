# Backend Development

The backend runs with local FastAPI and uses the already-started MySQL and
Redis containers for persistence.

## Requirements

- Python 3.12

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Set these values in `backend/.env` or your shell if they differ from defaults:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` and fill in `MYSQL_PASSWORD`, `SECRET_KEY`, and SMTP values.
Do not commit `.env`.

API docs:

- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/health

## Main APIs

- `POST /api/v1/auth/email-code` with `email` in JSON body or query string
- `POST /api/v1/auth/register` with `email`, `username`, `password`, `verification_code` in JSON body or query string
- `POST /api/v1/auth/login` with `email`, `password` in JSON body or query string; sets HttpOnly auth cookies
- `POST /api/v1/auth/refresh`; reads refresh token from HttpOnly cookie and resets auth cookies
- `POST /api/v1/auth/logout`; reads tokens from HttpOnly cookies, revokes them, and clears cookies
- `POST /api/v1/auth/wechat-login`
- `GET /api/v1/auth/me`
- `GET /api/v1/profile`
- `POST /api/v1/profile` with JSON body or query string
- `PATCH /api/v1/profile` with JSON body or query string
- `DELETE /api/v1/profile`
- `POST /api/v1/analyze/image` with image as multipart file; `question` can be form field or query string
- `POST /api/v1/analyze/text` with JSON body or query string
- `GET|POST /api/v1/analyze/result` with `task_id` in JSON body or query string
- `GET /api/v1/analyze/{task_id}`
- `GET /api/v1/analyze`

`/api/v1/analyze/*` currently returns a rule-based development result. Replace
`app.services.analyze_service.run_development_analysis` with Celery and the
algorithm gRPC service when those services are ready.

Auth tokens are not returned in response bodies. Frontend requests must include
cookies, for example `fetch(url, { credentials: "include" })`.
