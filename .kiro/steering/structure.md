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
│   │   ├── agents/
│   │   ├── workflows/
│   │   └── core/
│   ├── tests/
│   ├── Dockerfile
│   ├── Dockerfile.agent
│   └── pyproject.toml
│
├── infrastructure/
│   ├── terraform/
│   │   ├── modules/
│   │   │   ├── networking/
│   │   │   ├── ecs/
│   │   │   ├── alb/
│   │   │   ├── ecr/
│   │   │   ├── cognito/
│   │   │   ├── storage/
│   │   │   ├── database/
│   │   │   ├── messaging/        # SQS
│   │   │   ├── ai/               # Bedrock KB/GraphRAG + AgentCore Runtime
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

### Agents and workflows

LangGraph graph definitions (nodes, state, edges) and AgentCore deployment
configuration belong in `agents/`. `workflows/` holds thin helpers that create
jobs, enqueue to SQS, and invoke AgentCore agents. Long-running execution runs
in LangGraph agents on AgentCore Runtime, triggered via SQS, rather than by
blocking FastAPI requests. Agents are packaged as their own container image,
separate from the FastAPI image.

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

Do not allow:
- router → raw boto3 everywhere
- frontend → AWS credentials
- service → HTTP framework-specific response objects unless necessary
- repository → business policy
- AI prompt code scattered through routers

Keep business logic independent from FastAPI wherever practical so it remains testable and portable.
