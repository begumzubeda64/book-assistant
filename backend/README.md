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
  agents/            Three ISOLATED LangGraph agents (one image each):
                       shared/, ingestion/, adaptive_reading/, discussion/
  mcp_server/        MCP tool server (isolated tool tier): server.py, tools/
  workflows/         Job creation / SQS enqueue / AgentCore invocation helpers
  models/            Domain models
tests/               pytest unit + API tests
```

## Images

- `Dockerfile` — FastAPI application
- `Dockerfile.mcp` — MCP tool server
- `agents/Dockerfile.ingestion` — ingestion agent
- `agents/Dockerfile.adaptive_reading` — adaptive-reading agent
- `agents/Dockerfile.discussion` — discussion agent

Each is built with `backend/` as the build context. See `docs/flow.md` for how
the tiers interact and `docs/decisions.md` for why they are isolated.

## Commands

```bash
uv sync                                   # install deps (incl. dev)
uv run uvicorn src.main:app --reload      # run locally
uv run pytest                             # tests
uv run ruff check .                        # lint
uv run mypy src                            # type-check
```
