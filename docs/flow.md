# Codebase Flow

A living map of how the system fits together and how a request/job flows through
it. Update this when a boundary, tier, or major flow changes.

## Three isolated tiers

The system is separated into three tiers that fail independently. The only links
between tiers are a queue/network boundary — never a shared process.

```
TIER 1 — Application            TIER 2 — Agents                 TIER 3 — Tools
──────────────────────         ──────────────────────          ──────────────────
FastAPI (backend/src)          3 LangGraph agents              MCP tool server
image: Dockerfile              images: agents/Dockerfile.*     image: Dockerfile.mcp
runs on: ECS Fargate           runs on: AgentCore Runtime      runs on: ECS/AgentCore
                               (one runtime per agent)
        │                              │                               │
        │  create job → SQS ──────────▶│  call tools over MCP ─────────▶│
        │  (or direct invoke)          │                               │
        ▼                              ▼                               ▼
   DynamoDB / S3                  Bedrock (LLM)                   AWS (KB/GraphRAG,
                                                                  S3, DynamoDB)
```

- **Tier 1 ↔ Tier 2** boundary is **SQS + the DynamoDB job record** (async
  agents) or a direct AgentCore invoke (discussion). If an agent fails, the API
  keeps serving and the job goes to a retryable/`FAILED` state.
- **Tier 2 ↔ Tier 3** boundary is **MCP**. Agents have no direct AWS/business
  access; a tool failure is contained to the tool tier.
- **Within Tier 2**, the three agents are separate images/runtimes and share
  code only via `agents/shared/`.

## Application tier layering (FastAPI)

```
HTTP request
   → router (api/v1/*)            thin: routing, schemas, auth dependency, status
   → service (services/)          business use case
   → repository / integration     DynamoDB, S3, Cognito, book providers, SQS,
     (repositories/, integrations/)  AgentCore invoke client
```

Rules: routers stay thin; business logic lives in services; AWS SDK calls are
behind repositories/integrations; the application tier never imports agent graph
code.

## The three agents

| Agent | Package | Trigger | Job type | Output |
|-------|---------|---------|----------|--------|
| Ingestion | `agents/ingestion/` | SQS | `BOOK_INGESTION` | Prepared content in KB/graph; status in DynamoDB |
| Adaptive reading | `agents/adaptive_reading/` | SQS | `ADAPTIVE_READING` | Condensed reading in S3; status in DynamoDB |
| Discussion | `agents/discussion/` | Direct invoke | — | Grounded answer + references; message in DynamoDB |

Each agent is a LangGraph graph whose deterministic nodes are plain algorithms;
the model is called only where generation is actually required.

## Async job flow (ingestion, adaptive reading)

```
1. Frontend calls FastAPI (e.g. POST /api/v1/reading/generate)
2. Router → service validates + authorizes (Cognito user_id)
3. workflows/ helper creates a Job (DynamoDB, status=QUEUED) and enqueues to SQS
4. API returns { job_id } immediately  (never blocks)
5. The matching agent (its own AgentCore Runtime) consumes the SQS message
6. Agent runs its LangGraph graph, calling tools via the MCP server
7. Result → S3; job status → PROCESSING → COMPLETED (or FAILED) in DynamoDB
8. Frontend polls GET /api/v1/jobs/{job_id}; then reads the result
```

Idempotency: job creation uses an idempotency key / deterministic identity so
retries do not produce duplicate expensive results.

## Interactive discussion flow

```
1. Frontend posts a question (POST /api/v1/discussions/{id}/messages)
2. Router → service loads conversation context, authorizes the book access
3. service invokes the discussion agent directly (AgentCore)
4. agent runs GraphRAG retrieval via the MCP tool server → Bedrock generation
5. grounded answer + source references returned; message persisted in DynamoDB
```

## Tool tier (MCP server)

- Package: `mcp_server/` (server) + `mcp_server/tools/` (implementations).
- Exposes only allowlisted tools (e.g. GraphRAG retrieve, authorized-content
  access, concept persistence).
- Re-checks authorization on every call; never exposes arbitrary AWS APIs.

## Local development

Local-first (Approach B): the application tier runs against DynamoDB Local and
LocalStack (S3/SQS); Bedrock/GraphRAG and AgentCore are behind adapters that are
mocked locally and swapped for real clients once infrastructure exists.

```
docker compose up   → backend + dynamodb-local + localstack
frontend: npm run dev (proxies /api and /health to the backend)
```

## Current status

Milestone 1 (foundation) is in place: FastAPI app with `/health`, the `/api/v1`
router surface as stubs, the auth dependency seam, Docker images, the frontend
scaffold, and the Terraform skeleton. Agent packages, the MCP server, and real
AWS resources are implemented in later task groups (see
`.kiro/specs/mvp/tasks.md`).
