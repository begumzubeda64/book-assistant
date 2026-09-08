---
inclusion: always
---

# Development Steering

## How Kiro should work

Follow this order:

1. Read steering files.
2. Read the relevant MVP spec.
3. Inspect the existing code before changing it.
4. Implement the smallest complete vertical slice.
5. Add tests.
6. Validate locally.
7. Update documentation when architecture or behavior changes.

Kiro should not introduce a new AWS service, framework, database, library, or architectural pattern without a concrete requirement.

## Backend development rules

- Build a conventional FastAPI application.
- Keep routers thin.
- Put business logic in services.
- Abstract AWS SDK calls behind integrations/repositories.
- Use Pydantic models for API contracts.
- Use dependency injection for authenticated user context and service dependencies.
- Keep application services testable without a running AWS environment.
- Use async FastAPI endpoints where useful for I/O, but do not assume every boto3 call is async; isolate blocking SDK work appropriately.
- Never run long AI/document workflows inside an HTTP request.

## API conventions

- Prefix APIs with `/api/v1`.
- Return predictable JSON error structures.
- Use correct HTTP status codes.
- Add request IDs/correlation IDs.
- Provide `/health` for load-balancer health checks.
- Keep OpenAPI documentation accurate.
- Use pagination for potentially large lists.

## Async job rule

Any operation that may take more than a normal interactive request window must become a job.

Pattern:

`FastAPI → create job → SQS/Step Functions → processing → S3/DynamoDB → status/result`

The API returns a job ID without waiting for completion.

## Adaptive reading implementation

Adaptive reading must be an actual pipeline, not simple truncation. Use
deterministic algorithms wherever possible (word-budget allocation, section
scoring, source coverage, duplicate reduction). The full pipeline and the WPM
word-budget targets are defined in the MVP spec (`design.md`, "Components and
Interfaces → Adaptive reading") — follow them there rather than restating them
here.

## GraphRAG discussion implementation

GraphRAG is required in the MVP. Do not create a separate vector-only path to
simplify implementation; simple questions use the same managed retrieval path.
The retrieval flow is in the spec (`design.md`, "Components and Interfaces →
GraphRAG discussion").

## Recommendations

Start with transparent, testable scoring rather than a complex recommender
model, using signals such as category/author similarity, saved concepts, started
and completed books, reading-mode behavior, and metadata similarity. Document
the scoring formula and test it.

## Testing

Backend:
- pytest unit tests for services and algorithms.
- API tests for FastAPI routes.
- repository/integration tests where useful.
- authorization tests for every user-owned resource.
- async job state-transition tests.

Frontend:
- component tests for key flows.
- API integration tests for critical features.

Infrastructure:
- Terraform format/validate.
- static validation for IAM/network/security rules.
- deployment smoke tests.

End-to-end critical path:

`sign in → search book → open book → choose 5-minute reading → job completes → read result → ask question → receive grounded answer → progress saved → return and continue`

## Idempotency

Job creation and upload operations must be safe against retries. Use an idempotency key or deterministic job identity where duplicate work would create cost or inconsistent state.

## Definition of done

A feature is complete only when:
- requirements are satisfied
- implementation follows the architecture
- authorization is enforced
- tests exist
- errors are handled
- logs/metrics are adequate
- documentation is updated
- local development works
- Terraform is updated when infrastructure changes
- no unnecessary service or dependency was introduced
