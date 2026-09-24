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

### Authentication & authorization

```
request with Authorization: Bearer <jwt>
   → get_current_user dependency (api/dependencies.py)
       → CognitoJwtValidator (core/security/cognito.py)
           → verify RS256 signature against pool JWKS
           → verify exp / iss / token_use / audience(client_id)
           → claims → AuthenticatedUser(user_id = sub)
   → services use assert_owner(user, resource_owner_id)  (core/security/authorization.py)
       → mismatch → 403 FORBIDDEN ; missing → 404 NOT_FOUND
```

- The trusted `user_id` is the token `sub`; a client-supplied user id is never
  trusted (security requirement 1.3).
- Protected routes **fail closed**: if Cognito is unconfigured or the token is
  missing/invalid, the request is rejected with 401.
- Local development: an opt-in bypass (`AUTH_ALLOW_LOCAL_DEV_USER=true`) returns
  a fixed dev user, and only when `APP_ENV=local`. It is ignored everywhere else.
- Cognito User Pool + app client are provisioned by `modules/cognito`; the pool
  id and client id feed the backend as `COGNITO_USER_POOL_ID` /
  `COGNITO_CLIENT_ID`.

## The three agents

| Agent | Package | Trigger | Job type | Output |
|-------|---------|---------|----------|--------|
| Ingestion | `agents/ingestion/` | SQS | `BOOK_INGESTION` | Prepared content in KB/graph; status in DynamoDB |
| Adaptive reading | `agents/adaptive_reading/` | SQS | `ADAPTIVE_READING` | Condensed reading in S3; status in DynamoDB |
| Discussion | `agents/discussion/` | Direct invoke | — | Grounded answer + references; message in DynamoDB |

Each agent is a LangGraph graph whose deterministic nodes are plain algorithms;
the model is called only where generation is actually required.

## Authorized upload flow (implemented)

```
1. POST /api/v1/uploads/presign (auth; authorized_confirmation=true; pdf; size<=50MB)
   → UploadService.presign
   → S3Storage.presign_put -> short-lived presigned PUT for uploads/{user_id}/{book_id}.pdf
   → returns { book_id, upload_url, object_key }
2. Browser PUTs the PDF DIRECTLY to S3 (never through FastAPI)
3. POST /api/v1/books/{book_id}/ingest { object_key }
   → UploadService.complete_and_ingest
   → verify key belongs to user (prefix) and matches book_id; optional S3 existence check
   → JobService.create_and_enqueue(BOOK_INGESTION) — idempotent on "ingest:{object_key}"
   → Job (DynamoDB, QUEUED) + SQS message
   → returns { job_id, status }
```

- The uploads bucket is private (public access blocked); access only via
  presigned URLs. Keys are namespaced per user for server-side ownership checks.
- Backend config: `UPLOADS_BUCKET_NAME`, `JOBS_TABLE_NAME`, `JOBS_QUEUE_URL`
  (from Terraform `storage`/`database`/`messaging` outputs). Without a queue, a
  no-op queue is used locally; without a jobs table, job endpoints return 503.

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

## Reading progress flow (implemented)

```
PUT /api/v1/progress/{book_id} { position, chapter_id, selected_mode, completed } (auth)
   → progress router (api/v1/progress.py)
   → ProgressService.save_progress(user_id=<from token>, book_id, update)
   → DynamoDBProgressRepository.save  (PK user_id, SK book_id — idempotent upsert)

GET /api/v1/progress/{book_id} (auth)
   → ProgressService.get_progress(user_id, book_id)   (continue-reading entry point)
   → 404 PROGRESS_NOT_FOUND if none saved
```

- Progress is inherently self-scoped: the partition key is the token-derived
  `user_id`, so a user can only ever read/write their own progress (req 1.3).
- One item per (user, book): `PUT` is an idempotent upsert (req 6.1). Completion
  state is a `completed` flag (req 6.3).
- Backend config: `PROGRESS_TABLE_NAME` (Terraform `database` output); endpoint
  returns 503 if unset.

## Interactive discussion flow

```
1. Frontend posts a question (POST /api/v1/discussions/{id}/messages)
2. Router → service loads conversation context, authorizes the book access
3. service invokes the discussion agent directly (AgentCore)
4. agent runs GraphRAG retrieval via the MCP tool server → Bedrock generation
5. grounded answer + source references returned; message persisted in DynamoDB
```

## Ingestion pipeline (implemented — agent tier)

The ingestion agent (`agents/ingestion/`, its own image + AgentCore runtime)
consumes a `BOOK_INGESTION` SQS message and runs a LangGraph graph:

```
SQS BOOK_INGESTION → IngestionAgent.handle_message
  → job status PROCESSING (DynamoDB)
  → graph: fetch (MCP get_authorized_content → S3)
         → extract_text (pypdf, per page)
         → chunk_with_metadata (preserve chapter/section/page/source)
         → ingest (MCP ingest_to_knowledge_base)
             → write chunks to S3 under prepared/{user_id}/{book_id}/
             → start Bedrock KB ingestion job (Neptune Analytics GraphRAG)
  → job status COMPLETED (result_location = ingestion ref) or FAILED
```

- Deterministic nodes (extract/chunk) are plain algorithms; no model call.
- Agent reaches S3/Bedrock only through MCP tools (`get_authorized_content`,
  `ingest_to_knowledge_base`), which re-check ownership and preserve the
  per-user access boundary + source provenance for later scoped retrieval.
- Idempotent/retry-safe: terminal jobs are skipped on redelivery; chunk storage
  is keyed by (user, book).
- Config (agent/MCP tier): `UPLOADS_BUCKET_NAME`, `KB_CHUNK_BUCKET_NAME`,
  `KNOWLEDGE_BASE_ID`, `KNOWLEDGE_BASE_DATA_SOURCE_ID`.

## Tool tier (MCP server)

- Package: `mcp_server/` (FastMCP server) + `mcp_server/tools/`.
- `TOOL_ALLOWLIST` is the single source of truth for permitted tools.
- Implemented (ingestion): `get_authorized_content`, `ingest_to_knowledge_base`.
  GraphRAG retrieval + concept persistence are added with the discussion group.
- Re-checks authorization on every call; never exposes arbitrary AWS APIs.

## Book discovery flow (implemented)

```
GET /api/v1/books/search?q=... (auth required)
   → books router (api/v1/books.py)
   → BookDiscoveryService (services/book_discovery.py)
       → cache check (repositories/book_cache.py: DynamoDB or Null)
       → primary provider: Google Books ── on empty/error ──▶ fallback: Open Library
         (integrations/book_providers/*, normalized to schemas/books.BookMetadata)
       → warm cache (best-effort)
   → BookSearchResults
```

- Providers implement one `BookProvider` protocol and return the normalized
  `BookMetadata` shape (provider-agnostic).
- `book_id` is `"<provider>:<source_id>"`; `GET /books/{book_id}` routes to the
  matching provider (or the cache).
- Original reading time is estimated from word/page count at a default WPM,
  shown separately from adaptive reading time (requirement 4.1 / product.md).
- Discovery links are display-only; the underlying book is never ingested from
  them (requirement 2.4). Cache failures never fail a discovery request.

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
