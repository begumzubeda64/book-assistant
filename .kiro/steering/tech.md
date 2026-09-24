---
inclusion: always
---

# Technology Steering

This file records the technology decisions. Security rules live in `security.md`,
folder/layering rules in `structure.md`, and workflow/process rules in
`development.md`. Detailed runtime mechanics live in the MVP spec
(`.kiro/specs/mvp/design.md`).

## Architecture decision

The backend is **Python + FastAPI in Docker containers on Amazon ECS with AWS
Fargate**. This is an intentional change from the previous Lambda-only design:
FastAPI gives a conventional application framework (routing, dependency
injection, validation, OpenAPI, middleware, clean service layering) with local
development parity, and Fargate runs the containers without managing servers.

## Frontend

- React + TypeScript + Vite
- Tailwind CSS + shadcn/ui
- Built as static assets, hosted on S3, delivered through CloudFront

## Backend

- Python 3.11
- FastAPI + Pydantic v2
- Uvicorn/Gunicorn-compatible production container startup
- boto3 for AWS integrations
- LangGraph for agentic orchestration
- `bedrock-agentcore` SDK for building and deploying agents
- Model Context Protocol (MCP) for the agent tool boundary (tools run as a
  separate MCP server, not in-process with the agents)
- pytest, Ruff, mypy where useful

## Container platform

- Docker images stored in Amazon ECR
- Amazon ECS with the AWS Fargate launch type
- Application Load Balancer as the public entry point
- Multi-AZ, with ECS Service Auto Scaling
- CloudWatch for logs and metrics

The API is stateless. Persistent state belongs in managed AWS services.

## Networking

Use a VPC across at least two Availability Zones. Public subnets carry only the
internet-facing load balancer; ECS tasks run in private subnets. High-level path:

`CloudFront/S3 frontend → ALB → ECS Fargate FastAPI → AWS managed services`

Keep networking as simple as the MVP allows. (Network security invariants are in
`security.md`.)

## Data and storage

**DynamoDB** holds application state (users, books, user-book relationships,
reading progress, conversations, messages, jobs, recommendations, saved
concepts). Design tables around access patterns, not relational normalization.

**S3** holds large artifacts (authorized uploaded PDFs, extracted/prepared
content, generated adaptive-reading results). Upload privacy rules are in
`security.md`.

## AI

**Amazon Bedrock** provides foundation-model inference and embeddings.

**GraphRAG is a required MVP capability**, delivered through managed Bedrock
Knowledge Bases with **Neptune Analytics**. Use the graph for discussion and
retrieval that benefits from entity, concept, relationship, and evidence
traversal. A vector-only implementation must not be labelled GraphRAG. Neptune
Analytics is for GraphRAG knowledge representation, not the general application
database.

### Agentic AI

Agentic, multi-step work is built as **LangGraph** graphs and deployed on
**Amazon Bedrock AgentCore Runtime**, which hosts agents as container images,
isolates sessions, and scales them without managing servers. AgentCore Runtime
is framework-agnostic and available in `eu-central-1`. Deterministic steps stay
deterministic (see `development.md`).

**Isolation is a first-class architectural goal.** The system is separated into
three tiers that fail independently:

1. **Application tier** — the FastAPI service (its own image on ECS Fargate).
2. **Agent tier** — the LangGraph agents (on AgentCore Runtime).
3. **Tool tier** — the MCP tool server (its own image/process).

**Three agents, three isolated images.** There are exactly three LangGraph
agents, and each is packaged as its **own container image** deployed to its
**own AgentCore Runtime**, so they deploy, scale, version, and fail
independently — one agent cannot crash another, and each carries only its own
dependencies:

| Agent | Trigger | Job type |
|---|---|---|
| Ingestion agent | SQS (async) | `BOOK_INGESTION` |
| Adaptive-reading agent | SQS (async) | `ADAPTIVE_READING` |
| Discussion agent | Direct invoke (interactive) | — |

All three agent images are separate from the FastAPI image.

**Tools live in a separate MCP server, not in-process with the agents.** Agent
capabilities (e.g. GraphRAG retrieval, authorized-content access, concept
persistence) are exposed as explicit, allowlisted tools by a **Model Context
Protocol (MCP) server** that runs as its own image/process. Agents call tools
over MCP, so a misbehaving tool is contained to the tool tier and cannot crash
an agent or the API. The MCP server enforces the allowlist and never exposes
arbitrary AWS APIs (see `security.md`). This is a deliberate isolation choice
over an in-process tool design; see `decisions.md`.

**The deployment region is `eu-central-1` (Europe, Frankfurt).** All
infrastructure and AI services are provisioned there. Frankfurt is a supported
region for Bedrock Knowledge Bases GraphRAG with Neptune Analytics, so it
satisfies the required MVP GraphRAG capability. Confirm the specific
foundation-model availability in `eu-central-1` when selecting models.

## Async processing

Long-running work must never block an HTTP request. FastAPI creates a job,
returns a `job_id` immediately, and does not run ingestion or generation inline.
(The full pattern and rationale are in `development.md`; the workflow diagrams
are in the spec.)

Pattern: FastAPI creates a job → **SQS** durably queues it → the **matching
LangGraph agent on its own AgentCore Runtime** performs the multi-step work
(calling tools via the MCP server) → results go to **S3** and status to
**DynamoDB**. SQS plus the DynamoDB job record are the durable async boundary
(at-least-once delivery, retry, idempotency), and it is also the strong
isolation boundary between the application tier and the agent tier: if an agent
fails, the API keeps serving and the job moves to a retryable/`FAILED` state.
The multi-step orchestration itself lives in the LangGraph graph rather than in
Step Functions. AWS Step Functions and orchestration Lambda are not used in the
MVP; do not reintroduce them without a concrete requirement.

MVP job types: `BOOK_INGESTION` and `ADAPTIVE_READING`. Summary-style output is a
content *focus* of adaptive reading, not a separate job. (Podcast and audiobook
are out of scope — see `product.md`.)

## API

FastAPI exposes versioned REST endpoints (`/api/v1/...`) with generated OpenAPI
docs, plus `/health` for load-balancer checks. Endpoint groups: `books`,
`uploads`, `reading`, `discussions`, `recommendations`, `jobs`, `progress`. The
concrete API surface is defined in the spec and in Pydantic schemas.

## Infrastructure as Code

All infrastructure is owned by Terraform — networking, ALB, ECS, ECR (the
FastAPI image, one image per agent, and the MCP tool-server image), Cognito, S3,
DynamoDB, SQS, IAM, CloudWatch, Secrets Manager, CloudFront/S3 hosting, the
Bedrock/Knowledge Base/GraphRAG resources, and the AgentCore Runtime resources
(one per agent) with Terraform support. Do not hand-create production
infrastructure Terraform is meant to own. The module layout is in
`structure.md`.

## Observability

Use CloudWatch for container logs, ECS/ALB health, application and async-job
errors, latency, and AI workflow metrics. Use structured JSON logging.
(Logging restrictions are in `security.md`.)
