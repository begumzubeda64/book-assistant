# Book Companion — Backend

Conventional FastAPI application organized by domain
(`router → service → repository/integration`).

## Layout

```
src/
  main.py            FastAPI application entry point
  api/
    dependencies.py  Shared dependencies (auth, services)
    v1/              Versioned routers (books, uploads, reading, ...)
  core/              Config, logging, error handling, middleware
  schemas/           Pydantic request/response models
  services/          Business use cases
  repositories/      DynamoDB / persistence abstractions
  integrations/      External systems (S3, Cognito, book providers, SQS)
  ai/                Prompt construction, GraphRAG adapters, output validation
  agents/            LangGraph graph definitions + AgentCore config
  workflows/         Job creation / SQS enqueue / AgentCore invocation helpers
  models/            Domain models
tests/               pytest unit + API tests
```

## Commands

```bash
uv sync                                   # install deps (incl. dev)
uv run uvicorn src.main:app --reload      # run locally
uv run pytest                             # tests
uv run ruff check .                        # lint
uv run mypy src                            # type-check
```
