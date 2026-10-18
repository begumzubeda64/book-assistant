# Running the full flow locally (mock mode)

Local mock mode lets you click through the **entire** user journey — sign in,
discover, upload, adaptive reading, discussion, progress — on your machine with
**no AWS**. The AI output (readings and answers) is deterministic and clearly
marked as mocked; everything else behaves like the real app.

Book discovery (search) uses the real Google Books / Open Library public APIs,
so that part is genuinely live even in mock mode.

## What mock mode does

- Runs the async agents **inline** (no SQS / AgentCore) so jobs complete
  immediately.
- Keeps all state **in memory** (uploads, jobs, progress, conversations,
  ingested chunks, reading results) for the life of the backend process.
- Uses a **deterministic mock generator** for adaptive reading and discussion,
  prefixed with `[local mock output — not real AI generation]`.
- Requires **no AWS credentials or services**.

> State is in-memory and per-process: restarting the backend clears uploaded
> books, jobs, and conversations.

## 1. Backend

```bash
cd backend
uv sync --extra dev
# PowerShell:
$env:APP_ENV="local"; $env:LOCAL_MOCK="true"; $env:AUTH_ALLOW_LOCAL_DEV_USER="true"
uv run uvicorn src.main:app --reload
# bash:
# APP_ENV=local LOCAL_MOCK=true AUTH_ALLOW_LOCAL_DEV_USER=true \
#   uv run uvicorn src.main:app --reload
```

Backend serves at `http://localhost:8000` (OpenAPI at `/docs`).

## 2. Frontend

```bash
cd frontend
npm install
# PowerShell:
$env:VITE_LOCAL_MOCK="true"; npm run dev
# bash:
# VITE_LOCAL_MOCK=true npm run dev
```

Frontend serves at `http://localhost:5173` and proxies the API to the backend.
`VITE_LOCAL_MOCK=true` shows the amber "local mock mode" banner. The default
auth mode is `local`, so "Continue as dev user" signs you in with no Cognito.

## 3. Click the journey

1. **Sign in** → "Continue as dev user".
2. **Discover** → search a real title/author/ISBN (live Google Books / Open
   Library).
3. **My Library** → upload a PDF, tick the authorization box, "Upload & ingest"
   → the ingestion job completes inline.
4. **Read** → pick Quick/Balanced/Deep + a focus → "Generate" → the reading
   result appears (mock-marked prose + source refs).
5. **Discuss** → ask a question → a grounded, mock-marked answer with citations.
6. **Continue reading** / progress reflects your last session.

## Switching back to real AWS

Unset `LOCAL_MOCK` (and `VITE_LOCAL_MOCK`) and provide the real AWS config
(`UPLOADS_BUCKET_NAME`, `JOBS_TABLE_NAME`, `JOBS_QUEUE_URL`,
`KNOWLEDGE_BASE_ID`, etc. from the Terraform outputs). The same code paths then
use the AWS-backed implementations — mock mode changes wiring only, not the
services.
