# Infrastructure Security Audit

Status of the security invariants from `.kiro/steering/security.md`, mapped to
where they are enforced. "Enforced" = codified in Terraform/app now; "Deferred"
= belongs to a module still in skeleton form (ECS/ALB/networking, provisioned in
the infrastructure task group).

## Network

| Invariant | Status | Where |
|-----------|--------|-------|
| ECS tasks in private subnets, no public IPs | **Enforced** | `modules/ecs` services set `assign_public_ip=false` in private subnets (`modules/networking`) |
| ALB is the only public entry point, HTTPS only | **Enforced** | `modules/alb`: internet-facing ALB, HTTPS listener (TLS 1.3 policy) + HTTP→HTTPS 301 redirect |
| Security groups restrict traffic to required paths | **Enforced** | ALB SG allows 80/443 from internet; tasks SG allows the app port **only from the ALB SG** |

## S3

| Invariant | Status | Where |
|-----------|--------|-------|
| Uploads/results/chunks buckets private | **Enforced** | `aws_s3_bucket_public_access_block` on all three buckets (storage, ai) |
| Access via short-lived presigned URLs only | **Enforced** | `S3Storage.presign_put` (15-min expiry); PDF never proxied through the API |
| Server-side ownership by key prefix | **Enforced** | `owns_key` / `build_upload_key` (per-user `uploads/{user_id}/…`) re-checked in the content MCP tool |
| Encryption + versioning | **Enforced** | SSE (AES256) + versioning on uploads; SSE on results/chunks |

## Identity & authorization

| Invariant | Status | Where |
|-----------|--------|-------|
| Cognito JWT validated server-side | **Enforced** | `CognitoJwtValidator` (sig/iss/aud/exp/token_use) |
| `user_id` from trusted claims, never client-supplied | **Enforced** | `get_current_user` → `sub` |
| Every user-owned resource ownership-checked | **Enforced** | `assert_owner` + user-scoped repos (jobs, progress, conversations, readings) |

## IAM least privilege (per tier)

| Invariant | Status | Where |
|-----------|--------|-------|
| KB role scoped to its bucket + graph + embed model | **Enforced** | `modules/ai` `aws_iam_role_policy.kb_policy` (no wildcards beyond the graph resource) |
| Separate least-privilege roles per tier (API / MCP) | **Enforced** | `modules/ecs`: distinct API + MCP task roles (API: scoped DynamoDB/S3/SQS; MCP: scoped S3 + Bedrock). Agent AgentCore roles added with the agent-runtime provisioning. |

## AI / cost-abuse

| Invariant | Status | Where |
|-----------|--------|-------|
| Agents cannot call arbitrary AWS; tools allowlisted | **Enforced** | `mcp_server` `TOOL_ALLOWLIST`; agents reach AWS only via MCP tools |
| GraphRAG retrieval scoped to the user | **Enforced** | `GraphRAGRetrievalTool` metadata filter (`user_id` + `book_id`) |
| Structured output validated before store/return | **Enforced** | reading `validate_output`; Pydantic validation on tool payloads |
| Expensive generation rate-limited / idempotent | **Enforced** | `enforce_ai_rate_limit` on reading/discussion; job idempotency keys |

## Logging

| Invariant | Status | Where |
|-----------|--------|-------|
| Never log secrets/tokens/credentials/raw book text | **Enforced** | Audit of all `logger.*` calls (only IDs/counts/status/error-type); guard tests in `test_logging_safety.py` |
| Safe error responses (no stack traces/AWS detail) | **Enforced** | centralized handlers in `core/errors.py` |

## Observability

| Invariant | Status | Where |
|-----------|--------|-------|
| CloudWatch logs + metrics + alarms | **Enforced** | `modules/observability`: log groups, app-error + job-failure metric filters, ALB 5xx alarm, SNS topic |

## Secrets

- No secrets committed. `.gitignore` covers `.env`, tfstate, `secrets.tfvars`,
  `*.auto.tfvars`, `*.tfvars.local`. Verified with `git ls-files` +
  `git check-ignore`. Committed `.tfvars` hold only region/env/project.
- Runtime secrets come from the ECS task environment / Secrets Manager.
