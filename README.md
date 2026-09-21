# Book Companion

Book Companion helps people who do not naturally read books to start, engage
with, and finish them by turning a large reading commitment into short,
meaningful sessions (approximately 3, 5, or 10 minutes) while preserving the
ideas, arguments, examples, and context that make a book valuable.

The MVP delivers three primary capabilities — **adaptive reading**, **GraphRAG
discussion**, and **recommendations** — supported by book discovery, authorized
PDF upload, asynchronous job processing, and reading-progress tracking.

See `.kiro/steering/` for product/tech/structure/security/development decisions
and `.kiro/specs/mvp/` for the MVP requirements, design, and task plan.

## Architecture (target)

```
React + TypeScript (S3 + CloudFront)
        │  HTTPS
        ▼
      Cognito → ALB → ECS Fargate (FastAPI)
        │
        ├── DynamoDB (state / jobs)
        ├── S3 (PDFs / generated results)
        ├── SQS (durable async queue)
        │      └── AgentCore Runtime (LangGraph agents) → Bedrock (LLM)
        └── Bedrock Knowledge Bases + Neptune Analytics (GraphRAG)
```

Region: **`eu-central-1` (Europe, Frankfurt)**.

## Repository layout

```
backend/          FastAPI application (routers → services → repositories)
frontend/         React + TypeScript + Vite frontend
infrastructure/   Terraform (networking, ECS, ALB, ECR, Cognito, storage, ...)
docs/             Documentation
scripts/          Helper scripts
.kiro/            Steering and MVP spec
```

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

### Tests

```bash
cd backend
uv run pytest
uv run ruff check .
uv run mypy src
```

## Status

Milestone 1 (foundation) in progress: repository structure, FastAPI skeleton,
frontend scaffold, and infrastructure module skeleton. Feature slices follow the
task plan in `.kiro/specs/mvp/tasks.md`.
