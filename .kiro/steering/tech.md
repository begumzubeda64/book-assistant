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

- Python 3.12
- FastAPI + Pydantic v2
- Uvicorn/Gunicorn-compatible production container startup
- boto3 for AWS integrations
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

Primitives: Step Functions for multi-step orchestration, SQS for durable
queuing, and Lambda for small event-driven steps. DynamoDB holds job status; S3
holds large results.

MVP job types: `BOOK_INGESTION` and `ADAPTIVE_READING`. Summary-style output is a
content *focus* of adaptive reading, not a separate job. (Podcast and audiobook
are out of scope — see `product.md`.)

## API

FastAPI exposes versioned REST endpoints (`/api/v1/...`) with generated OpenAPI
docs, plus `/health` for load-balancer checks. Endpoint groups: `books`,
`uploads`, `reading`, `discussions`, `recommendations`, `jobs`, `progress`. The
concrete API surface is defined in the spec and in Pydantic schemas.

## Infrastructure as Code

All infrastructure is owned by Terraform — networking, ALB, ECS, ECR, Cognito,
S3, DynamoDB, SQS, Step Functions, IAM, CloudWatch, Secrets Manager,
CloudFront/S3 hosting, and the Bedrock/Knowledge Base/GraphRAG resources with
Terraform support. Do not hand-create production infrastructure Terraform is
meant to own. The module layout is in `structure.md`.

## Observability

Use CloudWatch for container logs, ECS/ALB health, application and async-job
errors, latency, and AI workflow metrics. Use structured JSON logging.
(Logging restrictions are in `security.md`.)
