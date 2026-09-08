---
inclusion: always
---

# Security Steering

## Identity and authorization

- Use Amazon Cognito for authentication.
- Validate JWTs server-side in FastAPI.
- Resolve the authenticated `user_id` from trusted token claims.
- Never trust a client-supplied `user_id`.
- Every book, upload, conversation, progress record, saved concept, and job must be checked against the authenticated owner.

## Network security

- Run ECS tasks in private subnets.
- Do not assign public IPs to application tasks.
- Expose the API through an Application Load Balancer.
- Restrict security-group traffic to the required paths and ports.
- Use HTTPS for public traffic.
- Keep AWS service access on IAM roles and VPC endpoints/controlled egress where practical.

## Container security

- Use a minimal Python base image.
- Run the FastAPI process as a non-root user.
- Pin/lock dependencies.
- Scan images before deployment.
- Do not put AWS credentials in Docker images, source code, or environment files.
- Use ECS task roles for AWS API access.
- Keep secrets in AWS Secrets Manager or SSM Parameter Store as appropriate.

## S3 security

- Keep book uploads private.
- Block public access.
- Use short-lived presigned URLs for direct uploads/downloads.
- Validate object ownership and expected key prefixes server-side.
- Validate file type, size, and extension.
- Do not allow arbitrary URL ingestion.

## Upload and document security

- Only authorized user content may enter ingestion.
- Treat uploaded text as untrusted input.
- Protect prompts and system instructions from document-level prompt injection.
- Never let document text change authorization decisions or tool permissions.
- Preserve source identifiers and access boundaries during GraphRAG ingestion.

## GraphRAG security

- Retrieval must be scoped to content the authenticated user is allowed to access.
- Never expose another user's uploaded book or derived graph context.
- Do not return hidden system metadata.
- Answers should include source references when available.
- Do not fabricate citations.

## API security

- Validate all input with Pydantic.
- Enforce payload and upload limits.
- Use rate limiting/throttling at the edge where appropriate and application-level abuse controls for expensive AI operations.
- Use idempotency for job-creation operations where duplicate execution could be costly.
- Return safe error messages; do not expose stack traces in production.

## AI security

- Treat user prompts, book content, retrieved chunks, and model output as untrusted data.
- Separate system instructions from retrieved content.
- Do not permit the model to invoke arbitrary AWS APIs.
- Keep tool permissions explicit and allowlisted.
- Validate structured model output before storing or returning it.

## Logging

Never log:
- passwords
- access/refresh tokens
- AWS credentials
- secrets
- full private book text
- unnecessary personal data

Log safe identifiers, request IDs, job IDs, latency, status, error codes, and operational metadata.

## Copyright and access

The system must only process books the user is legally authorized to access. Do not bypass DRM, paywalls, authentication, or access restrictions. Search APIs may provide metadata and legitimate buy/borrow links, but those links are not permission to ingest the underlying book.

## Cost-abuse protection

AI generation can be expensive. Protect generation endpoints with:
- authentication
- request limits
- target-duration limits
- job quotas where appropriate
- idempotency
- status tracking
- monitoring and alerts
