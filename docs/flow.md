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
5. The dispatcher service polls SQS and invokes the matching agent runtime
   (bedrock-agentcore InvokeAgentRuntime), routing by job_type; it acks the
   message on success, leaves it for redelivery (→ DLQ) on failure
6. Agent runs its LangGraph graph, calling tools via the MCP server
7. Result → S3; job status → PROCESSING → COMPLETED (or FAILED) in DynamoDB
8. Frontend polls GET /api/v1/jobs/{job_id}; then reads the result
```

Idempotency: job creation uses an idempotency key / deterministic identity so
retries do not produce duplicate expensive results.

Cold-start/reliability: agents are warmed on login (`POST /api/v1/warmup` → the
API background-pings each agent runtime, which returns `{"status":"warm"}`
immediately). The dispatcher's AgentCore invoke is bounded (`read_timeout=120`)
and the SQS visibility timeout is 180s (not 900s), so a cold/slow run can't pin a
message for a long lock; on timeout the message redelivers and the idempotent
agent reconciles (see `docs/decisions.md`).

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

## Discussion flow (implemented — agent tier, invoked directly)

Unlike ingestion/reading (async, SQS), the discussion agent is invoked directly
for short interactive turns (design.md).

```
POST /api/v1/discussions { book_id }               → create conversation (DynamoDB, user-scoped)
POST /api/v1/discussions/{id}/messages { question } (auth)
  → DiscussionService.post_message
      → load conversation (ownership-checked) + prior turns as context
      → DiscussionAgent.answer (LangGraph, invoked directly):
          retrieve (MCP graphrag_retrieve → Bedrock KB, filtered to user_id+book_id)
          → generate (MCP generate_text, grounded prompt: answer ONLY from sources)
          → citations (derived from retrieved passages — never fabricated)
      → persist user question + assistant answer (+citations) to DynamoDB
  → grounded MessageResponse with source references
GET /api/v1/discussions               → list a book's conversations (summaries)
GET /api/v1/discussions/{id}           → ConversationResponse (user-scoped)
```

- Retrieval is scoped to `user_id` + `book_id`, so a user never sees another
  user's book or graph context (security.md). Cross-chapter questions work
  because GraphRAG connects concepts across the book.
- Citations come only from retrieved passages; if no sources are found the
  answer says so rather than inventing facts.
- **Memory management:** older turns beyond a verbatim window are folded into a
  running `summary` (stored on the conversation) so long threads stay within the
  context window; the summary + recent turns + sources form the grounded prompt.
- **Titling:** the agent returns a short intent-based `title` alongside the
  answer. It is (re)generated during the opening turns and for as long as the
  stored title is still a placeholder ("General chat"/none), so a later topic
  replaces it; then it stabilizes. The frontend shows an instant question-derived
  title on send, replaced by the agent's title on the response (see
  `docs/decisions.md`).
- **Persona:** a conversation carries an optional `persona` (voice/style), chosen
  at creation and defaulting to a natural podcast host. The persona's voice is
  injected into the grounded prompt (`agents/discussion/personas.py`) so the
  answer reads like a human discussion — it changes delivery, never the facts or
  citations. `GET /api/v1/discussions/personas` lists the options; the persona is
  shown on the discussion list and chat header. Available: Podcast Host
  (default), Scholar, Coach, Skeptic, Storyteller.
- **Streaming:** the answer is returned whole and revealed progressively in the
  UI (typewriter), not streamed token-by-token end to end (see
  `docs/decisions.md` for the tradeoff).
- Config: `CONVERSATIONS_TABLE_NAME`, `KNOWLEDGE_BASE_ID`, `GENERATION_MODEL_ID`.

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

## Adaptive reading pipeline (implemented — agent tier)

The adaptive-reading agent (`agents/adaptive_reading/`, its own image) consumes
an `ADAPTIVE_READING` SQS job and runs a LangGraph graph. Only the generate node
calls the model; everything else is a deterministic algorithm (design.md).

```
POST /api/v1/reading/generate (auth; duration 3/5/10, mode, focus)
  → JobService.create_and_enqueue(ADAPTIVE_READING)  (idempotent) → job_id
  → SQS → AdaptiveReadingAgent.handle_message → job PROCESSING
      → load    (MCP get_book_content → prepared chunks)
      → budget  (150 WPM → 450 / 750 / 1500 words)
      → select  (rank by position + headings + argument/evidence + centrality
                 + focus, then pick to budget, restore reading order)
      → generate (MCP generate_text → coherent condensed prose)  [only model call]
      → validate (reject empty / bullet-dump / gross overrun)
      → refs     (dedupe source references)
      → store   (MCP store_reading_result → S3 readings/{user}/{reading_id}.json)
  → job COMPLETED (result_location) or FAILED

GET /api/v1/reading/{reading_id} → S3ReadingResultRepository (user-scoped) → ReadingResult
```

- reading_id == job_id. Ranking never just takes the first N words.
- Output is coherent prose within a generous word-budget tolerance (req 4.5);
  source references are retained (req 4.6).
- Config: `KB_CHUNK_BUCKET_NAME`, `READING_RESULTS_BUCKET_NAME`,
  `GENERATION_MODEL_ID`.

## Tool tier (MCP server)

- Package: `mcp_server/` (FastMCP server) + `mcp_server/tools/`.
- `TOOL_ALLOWLIST` is the single source of truth for permitted tools.
- Implemented: `get_authorized_content`, `ingest_to_knowledge_base`,
  `get_book_content`, `generate_text`, `store_reading_result`,
  `graphrag_retrieve`. Concept persistence is added with the recommendations group.
- `generate_text` is the single model-calling capability; agents never invoke
  Bedrock directly.
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

## Frontend (implemented — group 12)

React + TypeScript + Vite + Tailwind, built against the stable backend API
contracts. Local-dev-first auth: `VITE_AUTH_MODE=local` (default) treats the
session as a dev user and relies on the backend's local auth bypass (no token);
the real Cognito path is scaffolded behind `VITE_AUTH_MODE=cognito`.

```
src/
  app/            App (ErrorBoundary → AuthProvider → RouterProvider), router
  components/     Layout, ProtectedRoute, states (Spinner/Error/Empty),
                  ErrorBoundary, NotFoundPage
  features/
    auth/         AuthProvider + useAuth (token provider registered on api client)
    books/        DiscoverPage (search), BookDetailPage, BookCard
    reading/      LibraryPage + UploadBook + LibraryBookRow (progress),
                  ReadingConfigPage (3/5/10 · mode · focus), ReadingPage (result)
    discussion/   DiscussionStartPage, DiscussionPage (grounded chat + citations)
    recommendations/ RecommendationsPage (coming-soon until group 11)
  services/       Typed clients per domain over apiFetch (auto bearer / bypass)
  types/          TS mirrors of the backend Pydantic schemas
  stores/         uploadedBooks (localStorage registry — no list-my-books API)
```

User journey wired end to end: sign in → discover/search → upload authorized PDF
(presign → direct-to-S3 → ingest → job progress) → configure & generate adaptive
reading (job polling) → read result with source refs → discuss (GraphRAG chat) →
progress saved → continue reading. Async work uses `pollJob`; the PDF uploads
directly to S3, never through the API. All screens use shared loading/empty/
error/retry states.

Live-deploy UX/reliability behaviors layered on top:
- **Auth expiry:** an absent/expired token or any 401 clears the local session
  and routes to `/login` (the deliberate "Sign out" still uses the Hosted UI
  logout). Token validity is re-checked on mount and tab focus. The nav shows
  "Sign in" when logged out.
- **On-login warm-up:** `AuthCallbackPage` calls `POST /api/v1/warmup` to hide
  agent cold starts behind the first navigation.
- **Library freshness:** rows re-fetch progress/discussions/readings on tab
  focus/visibility; a local "reading started" flag makes "Continue reading"
  appear the instant generation is kicked off (see `docs/decisions.md`).
- **Reading generation** runs in the background with a non-blocking status; the
  user is never force-navigated and can open the result when it's ready.
- **Markdown** model output is rendered sanitized (`marked` + `DOMPurify`); all
  errors are mapped to friendly messages (`services/errors.ts`).
- **Remove book:** `DELETE /api/v1/books/{id}` with a client store cleanup.

Note: real end-to-end runtime needs the backend running with configured AWS
(uploads/jobs/KB/etc.); the UI builds, boots, and is contract-correct now.

## Local development

Local-first (Approach B): the application tier runs against DynamoDB Local and
LocalStack (S3/SQS); Bedrock/GraphRAG and AgentCore are behind adapters that are
mocked locally and swapped for real clients once infrastructure exists.

```
docker compose up   → backend + dynamodb-local + localstack
frontend: npm run dev (proxies /api and /health to the backend)
```

## Current status

Implemented and tested (backend, local-first):
- Foundation: FastAPI app, `/health`, request-ID middleware, error envelope.
- Auth: Cognito JWT validation + ownership authorization.
- Book discovery (Google Books + Open Library).
- Authorized upload + async job model/queue/status.
- Ingestion agent + GraphRAG KB (MCP tools).
- Adaptive-reading agent (3/5/10-minute pipeline).
- Discussion agent (GraphRAG, grounded answers) + conversation persistence.
- Reading progress.
- Terraform: cognito, storage, messaging, database, ai (GraphRAG) modules.

Implemented (frontend):
- **Frontend (group 12)** — React app: auth (local-dev bypass), discovery,
  upload flow, adaptive reading, discussion chat, progress/continue-reading,
  recommendations.

Also implemented:
- **Recommendations (group 11)** — transparent additive scoring endpoint
  (`GET /api/v1/recommendations`), no agent; each item carries a reason. Signals
  provider is a minimal stub until a reading-history store exists (see
  `docs/decisions.md`).

Also implemented:
- **Hardening (group 13)** — per-user AI rate limiting on expensive endpoints
  (reading generate, discussion message), safe-logging guard tests, observability
  Terraform module (CloudWatch log groups, app-error + job-failure metric
  filters, ALB 5xx alarm, SNS topic), and a security audit in
  `infrastructure/SECURITY.md`.

Also implemented:
- **CI/CD (group 14)** — GitHub Actions: `ci.yml` (backend ruff/mypy/pytest,
  frontend lint/build, terraform fmt/validate), `build.yml` (5 images + Trivy
  scan + OIDC ECR push), `deploy.yml` (terraform plan + ECS rolling deploy,
  `prod` gated by a GitHub Environment). AWS steps gated on `AWS_ROLE_ARN` so CI
  is green pre-AWS. See `.github/workflows/README.md`.

Also implemented:
- **E2E validation (group 15)** — `scripts/e2e_smoke.py` drives the full happy
  path over HTTP (search → upload → ingest → 5-min reading → cross-chapter
  question → progress/continue → unauthorized-access rejected); 16/16 checks pass
  against local-mock. Real-AWS run is the same script post-deploy. Checklist in
  `docs/e2e-validation.md`.
- **Portfolio (group 16)** — `docs/architecture.md` (diagram + tradeoffs),
  README polish (summary, features, docs index), `docs/screenshots/` capture
  guide, and a cleanup pass (removed redundant `.gitkeep`s; hardened two tests).

Also implemented:
- **Compute/network infra** — `modules/networking` (VPC, 2-AZ public/private
  subnets, NAT, SGs), `modules/alb` (HTTPS + redirect, `/health` target group),
  `modules/ecs` (Fargate API + MCP services, private no-public-IP tasks,
  least-privilege roles, autoscaling), `modules/ecr` (5 repos). ALB/ECS gated on
  `certificate_arn`.
- **AgentCore runtimes** — `modules/ai` creates 3 `awscc_bedrockagentcore_runtime`
  (one per agent) + least-privilege exec role, gated on `deploy_agents`.
- **Frontend hosting** — `modules/storage` adds a private S3 bucket + CloudFront
  (OAC, SPA fallback).
- **Cognito Hosted UI auth** — frontend authorization-code + PKCE flow
  (`features/auth/cognito.ts`, `/auth/callback`), token sent as bearer.
- **Dispatcher (SQS→AgentCore bridge)** — `workflows/dispatcher.py` +
  `integrations/agentcore.py`; its own ECS service (reuses the API image,
  dispatcher entrypoint) that polls SQS and invokes the matching agent runtime,
  routing by job_type with ack-on-success / redelivery-on-failure.
- `terraform validate` passes; frontend build+lint clean; 142 backend tests pass.

Remaining (needs AWS account / manual):
- ACM cert + DNS, Cognito Hosted UI domain + app-client URLs.
- `terraform apply` (two-stage) + image push + frontend publish + live e2e run;
  capture screenshots/GIF.
- Live AWS provisioning / real Bedrock+Neptune runs are deploy-time.
