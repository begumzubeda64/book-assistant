# MVP Design — Book Companion

## Overview

Book Companion makes books approachable by turning a large reading commitment
into short, meaningful sessions (approximately 3, 5, or 10 minutes) while
preserving the ideas, arguments, and context that make a book valuable. This
document describes how the MVP is built: the architecture, the AWS runtime, the
components and their interfaces, the data model, and the cross-cutting concerns
(correctness, error handling, testing). It implements the behavior defined in
`requirements.md` and follows the decisions in `.kiro/steering/`.

The system has three primary capabilities — **adaptive reading**, **GraphRAG
discussion**, and **recommendations** — supported by book discovery, authorized
PDF upload, asynchronous job processing, and reading-progress tracking.

### Why ECS Fargate + FastAPI

The product has multiple API domains, authentication dependencies, validation,
OpenAPI contracts, shared middleware, and non-trivial application services, so it
benefits from a real backend framework rather than a Lambda-only design.

FastAPI provides explicit API routing, Pydantic validation, dependency
injection, middleware, OpenAPI documentation, easy local execution, and a clean
separation between HTTP and business logic.

ECS Fargate provides containerized deployment with no EC2 server management,
horizontal service scaling, health checks, predictable runtime behavior, and
local Docker-to-production parity.

This is still a managed AWS architecture in the sense that Fargate removes server
management; it is simply not a Lambda-only architecture.

## Architecture

```text
                         React + TypeScript
                                │
                         CloudFront + S3
                                │
                             Cognito
                                │
                              HTTPS
                                │
                               ALB
                                │
                    ECS Fargate FastAPI Service
                                │
        ┌───────────────────────┼────────────────────────┐
        ▼                       ▼                        ▼
    DynamoDB                   S3                     AWS AI
        │                       │                        │
        │                       ├──────────────┐         │
        │                       ▼              │         ▼
        │                 SQS / Step Functions │   Bedrock Knowledge
        │                       │              │   Bases + Neptune
        │                       ▼              │   Analytics GraphRAG
        │                Lambda/workflows      │
        │                       │              │
        └───────────────────────┴──────────────┴─────────┘
```

The API is a conventional FastAPI application deployed as an ECS Fargate service,
fronted by an ALB and combined with Cognito, DynamoDB, ECR, and CloudWatch — a
standard containerized web architecture on AWS.

### Runtime components

| Component | Responsibility |
|---|---|
| React/S3/CloudFront | Frontend |
| Cognito | Authentication |
| ALB | HTTPS termination, routing, health checks |
| ECS/Fargate | FastAPI runtime |
| ECR | Container image registry |
| DynamoDB | Application state |
| S3 | PDFs and generated artifacts |
| SQS | Durable asynchronous queue |
| Step Functions | Multi-step orchestration |
| Lambda | Small event-driven workflow steps |
| Bedrock | LLM inference |
| Bedrock Knowledge Bases + Neptune Analytics | GraphRAG retrieval |
| CloudWatch | Logs/metrics/alarms |
| Secrets Manager | Secrets |
| Terraform | Infrastructure as code |

### Region

The deployment region is fixed at **`eu-central-1` (Europe, Frankfurt)**. All
infrastructure, data, and AI services are provisioned there.

Frankfurt is a supported region for Bedrock Knowledge Bases GraphRAG with
Neptune Analytics, so the required GraphRAG capability is available in-region.
When selecting foundation models, confirm the specific model IDs are available
in `eu-central-1` (model availability is narrower than service availability).

### Networking

Recommended MVP network:
- VPC
- two or more AZs
- public subnets for ALB
- private subnets for ECS tasks
- security groups limiting inbound traffic
- controlled outbound access for ECS tasks
- VPC endpoints for AWS services where cost/operational tradeoffs justify them

For the MVP, avoid unnecessary network complexity. The important invariant is
that ECS tasks are private and the ALB is the public application entry point.

### FastAPI application layering

```text
HTTP request
   ↓
FastAPI router
   ↓
Auth / validation dependencies
   ↓
Application service
   ↓
Repository / AWS integration
   ↓
DynamoDB / S3 / Bedrock / SQS / Step Functions
```

The FastAPI layer must not become a place where all business logic accumulates.

### Security boundaries

Security rules are defined in `.kiro/steering/security.md`. The design must
uphold the key invariants:
- ECS tasks run in private subnets with no public IPs; the ALB is the only public
  entry point, over HTTPS.
- Every user-owned resource (books, uploads, conversations, progress, jobs,
  saved concepts) is authorization-checked against the Cognito-derived `user_id`.
- Uploaded PDFs stay private in S3; access is via short-lived presigned URLs.
- GraphRAG retrieval is scoped to content the authenticated user may access.

### Observability

Track: request latency, HTTP status distribution, ECS task health, ALB target
health, job success/failure, Bedrock latency/errors, GraphRAG retrieval
failures, upload failures, and authorization failures. Use structured logs and
correlation/request IDs.

## Components and Interfaces

Each capability is realized as a `router → service → repository/integration`
slice. The flows below describe how the components interact.

### Authentication

```text
User → Cognito login → JWT → Frontend API request → ALB
     → FastAPI auth dependency → JWT validation → Authenticated user context
```

The backend uses the authenticated subject/user ID for all ownership checks.

### Book discovery

```text
User searches title/author/ISBN → FastAPI /books/search
     → Book discovery integration → Google Books / Open Library
     → Normalize metadata → Return metadata + legitimate links
```

External discovery providers are not trusted as authorization sources for
ingestion.

### Upload & ingestion

```text
Frontend → FastAPI requests upload URL → Authorization + validation
     → Presigned S3 URL → Browser uploads directly to S3
     → job trigger creates BOOK_INGESTION job → SQS → Step Functions
     → Extract/chunk/prepare content → Bedrock Knowledge Base ingestion
     → Neptune Analytics GraphRAG → DynamoDB job status
```

The PDF itself must not travel through FastAPI.

### Adaptive reading

```text
POST /api/v1/reading/generate → FastAPI validates request
     → Create ADAPTIVE_READING job → Return job_id → SQS / Step Functions
     → Load authorized chapter/content → Identify sections → Rank sections
     → Allocate target word budget → Generate coherent condensed reading
     → Validate output → Attach source references → Store result in S3
     → Update DynamoDB job
```

Ranking inputs: section position, headings, semantic importance,
argument/evidence indicators, repetition/centrality, and relationship to the
requested focus. Do not simply take the first N words.

Word-budget targets at a configurable default of 150 WPM:
- 3 minutes ≈ 450 words
- 5 minutes ≈ 750 words
- 10 minutes ≈ 1500 words

The generator may exceed or fall below the target slightly to preserve
coherence.

### GraphRAG discussion

```text
User question → FastAPI discussion endpoint → Conversation context
     → Bedrock Knowledge Base GraphRAG query
     → Neptune Analytics graph + vector retrieval
     → Relevant entities/concepts/relationships/source chunks
     → Bedrock generation → Grounded answer + source references
     → DynamoDB conversation persistence
```

GraphRAG is particularly useful for cross-chapter and relationship questions.

### Recommendations

Recommendations use transparent, testable scoring over signals already available
in the MVP (category/author similarity, saved concepts, started and completed
books, reading-mode behavior, metadata similarity). Results are computed by the
recommendation service and may be cached in DynamoDB. The scoring formula is
documented and unit-tested; see `development.md` for the scoring approach.

### API surface

```text
GET    /health
GET    /api/v1/books/search
GET    /api/v1/books/{book_id}
POST   /api/v1/uploads/presign
POST   /api/v1/books/{book_id}/ingest
GET    /api/v1/jobs/{job_id}
POST   /api/v1/reading/generate
GET    /api/v1/reading/{reading_id}
POST   /api/v1/discussions
POST   /api/v1/discussions/{conversation_id}/messages
GET    /api/v1/discussions/{conversation_id}
GET    /api/v1/progress/{book_id}
PUT    /api/v1/progress/{book_id}
GET    /api/v1/recommendations
```

Exact contracts are represented by Pydantic schemas and surfaced through OpenAPI.

## Data Models

Application state lives in DynamoDB; large artifacts live in S3. Tables are
designed around access patterns rather than relational normalization.

### DynamoDB access patterns

Required MVP access patterns:
- get user by ID
- get/search saved book metadata
- get user's book relationship
- get/update progress
- create/list conversations for user + book
- get conversation messages
- create/get job
- list user's recent jobs
- get recommendation results
- save/get concepts

Use appropriate partition/sort-key designs based on these patterns.

### Progress

A user's current reading state:

```text
user_id
book_id
chapter_id
position
selected_duration
selected_mode
completed
updated_at
```

### Job

```text
job_id
user_id
book_id
chapter_id
job_type
status
target_duration
mode
focus
progress
result_location
created_at
completed_at
error_code
```

States: `QUEUED → PROCESSING → COMPLETED`
Failure path: `QUEUED/PROCESSING → FAILED`

## Correctness Properties

- **Ownership isolation.** A user can never read or mutate another user's books,
  uploads, conversations, progress, jobs, or generated artifacts. Every access is
  checked against the Cognito-derived `user_id`.
- **Job idempotency.** Job creation and retries must not produce duplicate
  expensive results; use an idempotency key or deterministic job identity.
- **Progress idempotency.** Progress writes are idempotent and ownership-checked.
- **No blocking work.** Long-running ingestion or generation never runs inline in
  an HTTP request; the API returns a `job_id` immediately.
- **Coherent adaptive output.** Generated reading is coherent condensed prose
  within the word-budget target, not truncation or an unstructured bullet list.
- **Grounded answers.** Discussion answers are grounded in retrieved source
  material and include source references when available; citations are never
  fabricated.
- **Scoped retrieval.** GraphRAG retrieval only returns content the authenticated
  user is authorized to access.

## Error Handling

Use a consistent error structure:

```json
{
  "error": {
    "code": "BOOK_NOT_FOUND",
    "message": "The requested book could not be found",
    "request_id": "..."
  }
}
```

Never expose internal stack traces, AWS request details, or secrets. Async job
failures are recorded on the job record with an `error_code` and surfaced through
the job-status API rather than as an HTTP error on the original request.

## Testing Strategy

- Unit-test services and ranking/scoring algorithms.
- Test FastAPI routes with dependency overrides.
- Test authentication/authorization boundaries.
- Test repositories with mocks and selected integration tests.
- Test job state transitions and idempotency.
- Test GraphRAG integration behind an adapter.
- Test Docker build locally.
- Test Terraform validation.
- Run an end-to-end happy path before production deployment.
