# Implementation Plan

## Overview

This plan implements the Book Companion MVP defined in `requirements.md` and
`design.md`. It is organized into numbered, trackable task groups. Sub-tasks
reference the acceptance criteria in `requirements.md` (`_Requirements: N.M_`)
for traceability. Groups are ordered so that foundational work (repository,
FastAPI, infrastructure, authentication) precedes the feature slices, which in
turn precede frontend integration, hardening, CI/CD, and validation.

## Tasks

- [ ] 1. Repository and developer foundation
  - [ ] 1.1 Create repository structure from `structure.md`; add `.gitignore`, `.dockerignore`, README, and LICENSE.
  - [ ] 1.2 Initialize the Python project with `pyproject.toml`; add Ruff, pytest, and base test configuration.
  - [ ] 1.3 Initialize the React/Vite/TypeScript frontend.
  - [ ] 1.4 Add a Dockerfile for FastAPI and a Docker Compose setup for local development where useful.
  - [ ] 1.5 Add environment-variable configuration with safe defaults.
  - [ ] 1.6 Add a `/health` endpoint.
  - _Requirements: 10.1, 10.2_

- [ ] 2. FastAPI backend foundation
  - [ ] 2.1 Create the FastAPI application in `backend/src/main.py` and the `/api/v1` router structure.
  - [ ] 2.2 Add request ID/correlation middleware and centralized error handling.
  - [ ] 2.3 Add Pydantic base schemas and OpenAPI metadata/tags.
  - [ ] 2.4 Add the authentication dependency interface and service/repository dependency wiring.
  - [ ] 2.5 Add unit and API tests.
  - _Requirements: 9.3, 10.4, 10.5_

- [ ] 3. AWS container infrastructure (Terraform, `eu-central-1`)
  - [ ] 3.1 Create the VPC with two or more AZs, public subnets for the ALB, and private subnets for ECS tasks.
  - [ ] 3.2 Create the ECS cluster and two ECR repositories (FastAPI image, agent image), plus a CloudWatch log group.
  - [ ] 3.3 Create the ECS task execution role and a least-privilege task role.
  - [ ] 3.4 Create the Fargate task definition and ECS service with health checks.
  - [ ] 3.5 Create the ALB, target group, and HTTPS certificate.
  - [ ] 3.6 Provision the AgentCore Runtime (agent container image, execution role, endpoint) and the SQS queue for job triggering.
  - [ ] 3.7 Configure ECS service auto scaling and Terraform outputs for the API endpoint, ECR repositories, and AgentCore endpoint.
  - _Requirements: 9.1, 9.2, 9.5, 10.2, 10.3, 8.4_

- [ ] 4. Authentication
  - [ ] 4.1 Create the Cognito User Pool and app client configuration.
  - [ ] 4.2 Implement the FastAPI JWT validation dependency and authenticated-user context.
  - [ ] 4.3 Add an authorization helper for user-owned resources.
  - [ ] 4.4 Add the frontend authentication flow.
  - [ ] 4.5 Add auth integration tests.
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 5. Book discovery
  - [ ] 5.1 Implement the Google Books integration and Open Library fallback.
  - [ ] 5.2 Normalize metadata into a common schema and calculate original reading estimate when word count is available.
  - [ ] 5.3 Return legitimate buy/borrow links; do not accept arbitrary external URLs for ingestion.
  - [ ] 5.4 Cache normalized metadata in DynamoDB where useful.
  - [ ] 5.5 Add search API tests.
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 6. Authorized upload
  - [ ] 6.1 Create the private S3 bucket/prefix strategy with public access blocked.
  - [ ] 6.2 Implement the presigned upload endpoint with authorization confirmation and file type/size validation.
  - [ ] 6.3 Persist upload/book ownership metadata and implement upload completion validation.
  - [ ] 6.4 Create the `BOOK_INGESTION` job record and add the SQS queue.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 8.1_

- [ ] 7. Book ingestion and GraphRAG
  - [ ] 7.1 Build the LangGraph ingestion agent (content extraction/preparation node) triggered from SQS.
  - [ ] 7.2 Preserve chapter/section/page/source metadata where available.
  - [ ] 7.3 Configure the Bedrock Knowledge Base and Neptune Analytics GraphRAG integration in `eu-central-1`.
  - [ ] 7.4 Ingest authorized book content and store ingestion status in DynamoDB.
  - [ ] 7.5 Package and deploy the ingestion agent to AgentCore Runtime; add retry/idempotency handling.
  - [ ] 7.6 Test GraphRAG retrieval against representative book questions.
  - _Requirements: 5.2, 5.3, 8.2, 8.3, 8.4_

- [ ] 8. Adaptive reading
  - [ ] 8.1 Implement the reading request schema (duration, mode, focus).
  - [ ] 8.2 Implement the LangGraph adaptive-reading graph with deterministic nodes: word-budget calculation, section importance scoring, content selection.
  - [ ] 8.3 Implement the condensed-reading generation node, source-reference attachment, and output-validation node.
  - [ ] 8.4 Deploy the adaptive-reading agent to AgentCore Runtime (SQS-triggered for the `ADAPTIVE_READING` job) and store results in S3.
  - [ ] 8.5 Expose job status/result APIs.
  - [ ] 8.6 Add tests for the graph nodes and the 3/5/10-minute targets and coherence.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 8.4_

- [ ] 9. Discussion assistant
  - [ ] 9.1 Create the conversation/message DynamoDB model.
  - [ ] 9.2 Build the LangGraph discussion agent (GraphRAG query node) and deploy it to AgentCore Runtime; implement the discussion endpoint that invokes it.
  - [ ] 9.3 Add conversation context handling and generate grounded answers with source references.
  - [ ] 9.4 Persist messages.
  - [ ] 9.5 Add authorization tests and cross-chapter relationship test cases.
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 1.3, 8.4_

- [ ] 10. Reading progress
  - [ ] 10.1 Create the progress repository and save/update endpoint.
  - [ ] 10.2 Implement the continue-reading endpoint/data flow and track selected duration/mode.
  - [ ] 10.3 Add completion state.
  - [ ] 10.4 Add progress tests.
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 11. Recommendations
  - [x] 11.1 Define the transparent recommendation scoring formula.
  - [x] 11.2 Implement metadata similarity and user activity signals.
        (Signals provider is a minimal stub until a reading-history store exists.)
  - [x] 11.3 Implement the recommendation service and persist/cache results where useful.
  - [x] 11.4 Add explanation metadata and recommendation tests.
  - _Requirements: 7.1, 7.2_

- [x] 12. Frontend product experience
  - [x] 12.1 Build authentication, discovery/search, and book details screens.
  - [x] 12.2 Build the authorized PDF upload flow and reading configuration UI.
  - [x] 12.3 Build the adaptive reading result page and async job progress/status UI.
  - [x] 12.4 Build the discussion UI, continue-reading UI, and recommendations UI.
        (Recommendations UI is a "coming soon" stub until group 11 lands.)
  - [x] 12.5 Clearly display original vs selected reading time; add loading, empty, error, and retry states.
  - _Requirements: 2.2, 3.1, 4.1, 4.2, 4.3, 4.4, 5.1, 5.5, 6.2, 7.1_

- [x] 13. Security and observability
  - [x] 13.1 Review IAM policies for least privilege; confirm ECS tasks have no public IPs and S3 public access is blocked.
        (S3 blocks + KB IAM enforced now; ECS no-public-IP + per-tier roles deferred to the ECS/networking provisioning group — see `infrastructure/SECURITY.md`.)
  - [x] 13.2 Confirm secrets are not in source/image/environment files.
  - [x] 13.3 Add CloudWatch alarms for ECS/ALB failures, application error metrics, and async job failure metrics.
  - [x] 13.4 Add safe structured logging and AI cost-abuse protections.
  - _Requirements: 9.1, 9.2, 9.4, 9.5, 8.3_

- [x] 14. CI/CD
  - [x] 14.1 Add the GitHub Actions lint/test workflow.
  - [x] 14.2 Build and security-scan the Docker images (api, mcp, 3 agents); authenticate to AWS via OIDC and push to ECR.
  - [x] 14.3 Deploy the ECS task definition/service; run Terraform fmt/validate/plan.
  - [x] 14.4 Add the environment-specific deployment workflow with a production approval gate.
        (AWS steps gated on `AWS_ROLE_ARN`; approval gate via the GitHub `production` Environment.)
  - _Requirements: 10.2_

- [~] 15. End-to-end validation
  - [x] 15.1 Sign in, search for a book, and open metadata/details.
  - [x] 15.2 Upload an authorized PDF and wait for the ingestion job to complete.
  - [x] 15.3 Generate a 5-minute balanced reading and read the result with source references.
  - [x] 15.4 Ask a cross-chapter question and verify a GraphRAG-grounded answer.
  - [x] 15.5 Save progress, return, and continue reading; verify recommendations.
  - [x] 15.6 Verify unauthorized resource access is rejected.
  - _Requirements: 1.3, 2.1, 3.3, 4.7, 5.4, 6.2, 7.1, 8.1_
  - _Automated by `scripts/e2e_smoke.py` + `docs/e2e-validation.md`; all 16 checks
    pass against local-mock. The run against **real AWS** is pending deployment
    (`terraform apply` + image push) — same script, different `--base-url`/token._

- [x] 16. Portfolio readiness
  - [x] 16.1 Document architecture and key tradeoffs (FastAPI + ECS/Fargate, GraphRAG, async jobs, security boundaries). (`docs/architecture.md`)
  - [x] 16.2 Document local development and deployment commands; add an architecture diagram and API/OpenAPI docs to the README.
  - [x] 16.3 Add screenshots/GIFs of the primary user journey and remove unused infrastructure and dependencies. (`docs/screenshots/` capture guide; image capture is a manual step.)
  - _Requirements: 10.1, 10.5_

## Task Dependency Graph

Ordering constraints between task groups (an arrow means "must complete before").

Waves execute sequentially; task groups within a wave have no dependencies on
each other and can run concurrently.

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1"], "dependsOn": [] },
    { "wave": 2, "tasks": ["2"], "dependsOn": ["1"] },
    { "wave": 3, "tasks": ["3", "4"], "dependsOn": ["2"] },
    { "wave": 4, "tasks": ["5", "6", "10"], "dependsOn": ["4"] },
    { "wave": 5, "tasks": ["7"], "dependsOn": ["6"] },
    { "wave": 6, "tasks": ["8", "9"], "dependsOn": ["7"] },
    { "wave": 7, "tasks": ["12"], "dependsOn": ["5", "6", "8", "9", "10"] },
    { "wave": 8, "tasks": ["11"], "dependsOn": ["5", "10"] },
    { "wave": 9, "tasks": ["13"], "dependsOn": ["11", "12"] },
    { "wave": 10, "tasks": ["14"], "dependsOn": ["13"] },
    { "wave": 11, "tasks": ["15"], "dependsOn": ["14"] },
    { "wave": 12, "tasks": ["16"], "dependsOn": ["15"] }
  ]
}
```

> **Reorder note (2026-09-21):** the frontend (group 12) was moved ahead of
> recommendations (group 11). Once the feature-backend API contracts (groups 5,
> 6, 8, 9, 10) are stable, the frontend no longer needs to wait on
> recommendations; group 12 builds against the stable contracts and stubs the
> recommendations screen until group 11 lands. Group 11 (a single scored
> endpoint, no agent) then slots in alongside/after the frontend, and hardening
> (group 13) waits on both. See `docs/decisions.md`.

```text
1  Repository foundation
        │
        ▼
2  FastAPI backend foundation
        │
        ├─────────────► 3  AWS container infrastructure
        │                       │
        ▼                       ▼
4  Authentication ◄─────────────┘
        │
        ├──────────────┬───────────────┬───────────────┐
        ▼              ▼               ▼               │
5  Book discovery  6  Authorized    10 Reading         │
        │             upload          progress         │
        │              │                                │
        │              ▼                                │
        │          7  Ingestion + GraphRAG              │
        │              │                                │
        │              ├───────────────┐                │
        │              ▼               ▼                │
        │          8  Adaptive     9  Discussion        │
        │             reading         assistant         │
        │              │               │                │
        └──────────────┴───────────────┴────────────────┤
                                                         ▼
                                              12  Frontend experience
                                                         │
                                              11  Recommendations
                                              (in parallel; frontend stubs it)
                                                         │
                                                         ▼
                                              13  Security & observability
                                                         │
                                                         ▼
                                              14  CI/CD
                                                         │
                                                         ▼
                                              15  End-to-end validation
                                                         │
                                                         ▼
                                              16  Portfolio readiness
```

Key dependencies:
- **2 → 3, 4**: application scaffolding precedes infrastructure and auth wiring.
- **4 → 5–11**: authentication and ownership checks gate every user-owned feature.
- **6 → 7**: a book must be uploaded before it can be ingested.
- **7 → 8, 9**: ingestion (content + GraphRAG graph) must exist before adaptive
  reading generation and GraphRAG discussion.
- **5, 6, 8, 9, 10 → 12**: the feature-backend contracts precede their frontend
  integration. The frontend does **not** depend on recommendations (11); it
  stubs that screen until 11 lands (reorder 2026-09-21).
- **5, 10 → 11**: recommendations scores over discovery/progress signals; it can
  run in parallel with the frontend.
- **11, 12 → 13 → 14 → 15**: hardening waits on both the frontend and
  recommendations, then CI/CD, then end-to-end validation.

## Notes

- **Region**: all infrastructure and AI services are provisioned in
  `eu-central-1` (see `design.md`, "Architecture → Region").
- **Async rule**: ingestion and adaptive-reading generation run as jobs
  (SQS → LangGraph agent on AgentCore Runtime → S3/DynamoDB), never inline in an
  HTTP request. Step Functions and orchestration Lambda are not used.
- **Idempotency**: job-creation and upload tasks (6, 7, 8) must be safe against
  retries; verify no duplicate expensive results are produced.
- **Authorization**: every user-owned resource task must include an authorization
  check and a corresponding test (Requirement 1.3).
- **Testing**: each feature group includes tests; the end-to-end happy path
  (group 15) is run before production deployment.
- **Traceability**: `_Requirements: N.M_` references map back to acceptance
  criteria in `requirements.md`; keep them updated if requirements change.
