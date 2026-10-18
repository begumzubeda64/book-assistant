# Book Companion

Book Companion helps people who do not naturally read books to start, engage
with, and finish them by turning a large reading commitment into short,
meaningful sessions (approximately 3, 5, or 10 minutes) while preserving the
ideas, arguments, examples, and context that make a book valuable.

> **In one line:** a React + FastAPI AI reading platform that turns owned books
> into coherent 3/5/10-minute adaptive readings, summaries, and GraphRAG-grounded
> Q&A — using LangGraph agentic AI on Amazon Bedrock AgentCore with an isolated
> MCP tool layer — to raise book completion and retention.

The MVP delivers three primary capabilities — **adaptive reading**, **GraphRAG
discussion**, and **recommendations** — supported by book discovery, authorized
PDF upload, asynchronous job processing, and reading-progress tracking.

The stack is **deployed and running on AWS** in `eu-central-1`. Adaptive reading,
GraphRAG discussion (with streaming answers and selectable personas), discovery,
upload, async jobs, and progress are working end to end. Recommendations is the
one feature not yet fully functional — the scoring is built and tested, but its
signals provider is still a stub (see Status below).

## Features

- **Adaptive reading** — Quick / Balanced / Deep (≈3/5/10 min) at 150 WPM, with a
  content focus (key ideas, arguments, summary, …). Coherent condensed prose with
  source references — not truncation.
- **GraphRAG discussion** — ask questions about an authorized book; answers are
  grounded in the book with chapter/page citations and connect ideas across it.
  Answers stream back in real time over SSE, with selectable conversation
  personas (Podcast Host, Scholar, Coach, Skeptic, Storyteller, The Wit) and
  smart, intent-based conversation titles.
- **Recommendations** — transparent, explainable scoring over your reading
  signals (each pick carries a reason). _Scoring is implemented and tested; the
  signals provider is currently a stub, so this feature is not yet fully
  functional end to end._
- **Discovery** — search by title/author/ISBN (Google Books + Open Library).
- **Authorized upload** — private per-user PDFs via short-lived presigned URLs;
  the file never passes through the API.
- **Async jobs & progress** — long work runs off the request path with visible
  status; progress is saved so you can continue later.

## Architecture

```
React + TypeScript (S3 + CloudFront)
        │  HTTPS
        ▼
      Cognito → ALB → ECS Fargate (FastAPI)
        │
        ├── DynamoDB (state / jobs)
        ├── S3 (PDFs / generated results)
        ├── SQS (durable async queue)
        │      └── AgentCore Runtime: 3 isolated LangGraph agents → MCP tools → Bedrock
        └── Bedrock Knowledge Bases + Neptune Analytics (GraphRAG)
```

Three isolated tiers (application / agents / MCP tools) that fail independently.
Region: **`eu-central-1` (Europe, Frankfurt)**. Full detail in
**[docs/architecture.md](docs/architecture.md)**.

### Deployment

The environment is deployed to AWS and released **manually**: build the five
container images tagged with the current git SHA, push to ECR, run
`terraform apply -var image_tag=<sha>`, then publish the frontend to S3 and
invalidate CloudFront. The frontend is served from CloudFront and the API from a
CloudFront distribution in front of the ALB. See
**[docs/deployment.md](docs/deployment.md)** for the runbook.

## Documentation

- [docs/architecture.md](docs/architecture.md) — architecture + diagram, tiers, tradeoffs
- [docs/flow.md](docs/flow.md) — codebase flow per feature
- [docs/decisions.md](docs/decisions.md) — key decisions and rationale
- [docs/local-mock.md](docs/local-mock.md) — run the whole flow locally, no AWS
- [docs/e2e-validation.md](docs/e2e-validation.md) — end-to-end happy-path checklist
- [docs/deployment.md](docs/deployment.md) — AWS deployment runbook

> Product/tech/security steering and the MVP spec live under `.kiro/` on the
> `dev` branch (not tracked on `main`).

## Repository layout

```
backend/          FastAPI application (routers → services → repositories)
frontend/         React + TypeScript + Vite frontend
infrastructure/   Terraform (networking, ECS, ALB, ECR, Cognito, storage, ...)
docs/             Documentation
scripts/          Helper scripts
```

> Steering and the MVP spec (`.kiro/`) are tracked on the `dev` branch only.

## Prerequisites

| Tool | Version used | Purpose |
|------|--------------|---------|
| Python | 3.11 | Backend runtime |
| uv | latest | Python dependency management |
| Node.js | 22.x | Frontend tooling |
| Docker | latest | Local containers / parity |
| Terraform | 1.16+ | Infrastructure as code |
| AWS CLI | v2 | AWS access |

## Local development

The MVP is built local-first: the backend runs against local/mocked AWS
(DynamoDB Local + LocalStack for S3/SQS) so features can be developed and tested
without a live AWS environment.

### Backend (without Docker)

```bash
cd backend
uv sync
uv run uvicorn src.main:app --reload
```

The API is served at `http://localhost:8000`; OpenAPI docs at
`http://localhost:8000/docs`; health check at `http://localhost:8000/health`.

### Full local stack (with Docker)

```bash
docker compose up --build
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies the API to :8000)
```

### Click the whole journey locally (no AWS)

Local **mock mode** runs the entire flow (upload → adaptive reading →
discussion → progress) in-process with in-memory fakes and clearly-marked mock
AI output — no AWS required. See **[docs/local-mock.md](docs/local-mock.md)**.

### Tests & checks

```bash
# Backend
cd backend
uv run ruff check . && uv run mypy src && uv run pytest

# Frontend
cd frontend
npm run lint && npm run build

# Infrastructure
cd infrastructure/terraform
terraform fmt -check -recursive && terraform init -backend=false && terraform validate

# End-to-end happy path (against a running backend)
python scripts/e2e_smoke.py --base-url http://localhost:8000
```

## Status

Deployed and running on AWS (`eu-central-1`). Working end to end: discovery,
authorized upload, async ingestion + GraphRAG, adaptive reading, GraphRAG
discussion (streaming answers + personas), and reading progress — with a React
frontend, CI/CD, and security/observability hardening.

**Not yet fully functional:** recommendations. The scoring logic
(`services/recommendation_scoring.py`) is implemented and unit-tested, but the
signals provider is a stub (no reading-history / saved-concepts store yet), so
the endpoint returns an empty list. Wiring the signals provider to real data is
a localized change that does not touch the scoring formula. See
[docs/decisions.md](docs/decisions.md).
