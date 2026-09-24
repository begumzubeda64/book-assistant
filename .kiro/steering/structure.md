---
inclusion: always
---

# Project Structure Steering

## Repository

```text
book-companion/
│
├── .kiro/
│   ├── steering/
│   │   ├── product.md
│   │   ├── tech.md
│   │   ├── structure.md
│   │   ├── security.md
│   │   └── development.md
│   └── specs/
│       └── mvp/
│           ├── requirements.md
│           ├── design.md
│           └── tasks.md
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── books/
│   │   │   ├── reading/
│   │   │   ├── discussion/
│   │   │   └── recommendations/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── stores/
│   │   ├── types/
│   │   └── utils/
│   ├── public/
│   ├── tests/
│   └── package.json
│
├── backend/
│   ├── src/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── dependencies.py
│   │   │   └── v1/
│   │   │       ├── books.py
│   │   │       ├── uploads.py
│   │   │       ├── reading.py
│   │   │       ├── discussions.py
│   │   │       ├── recommendations.py
│   │   │       ├── jobs.py
│   │   │       └── progress.py
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── ai/
│   │   ├── integrations/
│   │   ├── agents/               # one isolated LangGraph agent per subpackage
│   │   │   ├── shared/           # common graph/state/runtime helpers
│   │   │   ├── ingestion/
│   │   │   ├── adaptive_reading/
│   │   │   └── discussion/
│   │   ├── mcp_server/           # MCP tool server (separate deployable)
│   │   │   ├── server.py
│   │   │   └── tools/            # allowlisted tool implementations
│   │   ├── workflows/
│   │   └── core/
│   ├── tests/
│   ├── Dockerfile                # FastAPI application image
│   ├── Dockerfile.mcp            # MCP tool-server image
│   ├── agents/
│   │   ├── Dockerfile.ingestion
│   │   ├── Dockerfile.adaptive_reading
│   │   └── Dockerfile.discussion
│   └── pyproject.toml
│
├── infrastructure/
│   ├── terraform/
│   │   ├── modules/
│   │   │   ├── networking/
│   │   │   ├── ecs/              # FastAPI service (+ MCP tool server)
│   │   │   ├── alb/
│   │   │   ├── ecr/              # repos: api, mcp, 3 agent images
│   │   │   ├── cognito/
│   │   │   ├── storage/
│   │   │   ├── database/
│   │   │   ├── messaging/        # SQS
│   │   │   ├── ai/               # Bedrock KB/GraphRAG + 3 AgentCore Runtimes
│   │   │   └── observability/
│   │   ├── environments/
│   │   │   ├── dev/
│   │   │   └── prod/
│   │   └── main.tf
│   └── README.md
│
├── docs/
├── scripts/
├── .github/
│   └── workflows/
├── .dockerignore
├── .gitignore
├── docker-compose.yml
├── README.md
└── LICENSE
```

## Backend boundaries

Keep one FastAPI application, organized by domain rather than by deployment unit.

### Routers

Routers handle:
- HTTP routing
- request/response schemas
- authentication dependencies
- status codes
- lightweight request validation

Routers must not contain complex business logic or direct DynamoDB/Bedrock calls.

### Services

Services contain business use cases:
- book discovery
- upload authorization
- reading generation requests
- discussion orchestration
- recommendation scoring
- progress updates
- job management

### Repositories/integrations

Repositories abstract persistence and external systems:
- DynamoDB repositories
- S3 storage
- Cognito helpers
- Google Books/Open Library clients
- Bedrock/Knowledge Base client wrappers
- SQS client and AgentCore invocation client

### Schemas

Pydantic request/response schemas belong in `schemas/` and should be explicit.

### AI

AI-specific prompt construction, GraphRAG retrieval adapters, citation normalization, and output validation belong in `ai/`.

### Agents (isolated, one image each)

Each of the three LangGraph agents is an isolated subpackage under `agents/`
(`ingestion/`, `adaptive_reading/`, `discussion/`), with shared graph/state
helpers in `agents/shared/`. Each subpackage holds its own graph definition
(nodes, state, edges) and AgentCore deployment configuration, and is packaged as
its **own container image** (`agents/Dockerfile.<agent>`) deployed to its **own
AgentCore Runtime**. Agents deploy, scale, version, and fail independently; one
agent's code, dependencies, or failure must not affect another or the FastAPI
image.

Agents do not call AWS or business logic directly. They obtain capabilities
through the **MCP tool server** (see below). Long-running execution runs in the
agents on AgentCore Runtime, triggered via SQS, rather than by blocking FastAPI
requests.

### MCP tool server (isolated tool tier)

The `mcp_server/` package is a separate deployable (`Dockerfile.mcp`) that
exposes allowlisted agent capabilities over the Model Context Protocol —
GraphRAG retrieval, authorized-content access, concept persistence, and similar.
Tool implementations live in `mcp_server/tools/`. Running tools in their own
process/container isolates tool failures from the agents and the API, and gives
one enforced allowlist boundary (see `security.md`). Tools must not expose
arbitrary AWS APIs, and they re-check authorization; they never trust a caller
to have already done so.

### Workflows

`workflows/` holds thin helpers that create jobs, enqueue to SQS, and invoke the
correct AgentCore agent. It is the application-tier seam to the agent tier and
must stay thin (no orchestration logic — that lives in the LangGraph graphs).

## Naming

- Python: `snake_case` for modules/functions/variables.
- Python classes: `PascalCase`.
- API routes: plural nouns and versioned `/api/v1/...` paths.
- React components: `PascalCase.tsx`.
- Terraform modules: lowercase descriptive names.
- Tests: mirror source names and use `test_*.py` or `*.test.ts(x)`.

## Dependency rule

Prefer:

`router → service → repository/integration`

Agent tier:

`agent (LangGraph graph) → MCP tool server → AWS`

Do not allow:
- router → raw boto3 everywhere
- frontend → AWS credentials
- service → HTTP framework-specific response objects unless necessary
- repository → business policy
- AI prompt code scattered through routers
- agent → direct AWS/boto3 or business logic (must go through the MCP tool server)
- application tier → importing agent graph code (cross the boundary via SQS/invoke only)
- one agent → importing another agent's code (share only via `agents/shared/`)

Keep business logic independent from FastAPI wherever practical so it remains testable and portable.
