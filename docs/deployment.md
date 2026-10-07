# Deployment Runbook

How to take Book Companion from the repo to a running stack in **`eu-central-1`**.

> **Status note — read first.** The application code (FastAPI, 3 agents, MCP
> server), and the Terraform modules for **cognito, storage, database (DynamoDB),
> messaging (SQS), ai (Bedrock KB + Neptune Analytics GraphRAG), ecr, and
> observability** are implemented. The **networking, ecs, and alb** modules are
> still skeletons (deferred). Steps that depend on them are marked
> **[needs infra]** and require implementing those modules first (see
> `infrastructure/SECURITY.md` → "Deferred"). Everything else can be provisioned
> today.

## 0. Prerequisites

- AWS account with access to Bedrock (models + Knowledge Bases), Neptune
  Analytics, ECS/Fargate, and AgentCore in `eu-central-1`.
- Tools: Terraform ≥ 1.16, AWS CLI v2, Docker, authenticated AWS credentials.
- **Confirm model availability in `eu-central-1`** for the embedding model
  (`amazon.titan-embed-text-v2:0`) and the generation model
  (`anthropic.claude-3-5-sonnet-...`); request access in the Bedrock console if
  needed. Adjust `generation_model_id` / `embedding_model_arn` if a model isn't
  available in-region.

## 1. Remote state (recommended, one-time)

Create an S3 bucket + DynamoDB lock table for Terraform state, then add a
`backend "s3"` block to `infrastructure/terraform` (not committed with real
values). Until then, state is local.

## 2. Provision infrastructure

```bash
cd infrastructure/terraform
terraform init
terraform plan  -var-file=environments/dev/dev.tfvars
terraform apply -var-file=environments/dev/dev.tfvars
```

This creates (today): Cognito user pool + client, S3 buckets (uploads, reading
results, KB chunks — all public-access-blocked), DynamoDB tables (jobs,
progress, conversations), SQS job queue + DLQ, the Bedrock Knowledge Base +
Neptune Analytics graph, ECR repositories, and CloudWatch alarms.

**[needs infra]** Networking (VPC/subnets/SGs), the ECS cluster + Fargate
service + task roles, and the ALB are added when those modules are implemented.

### Capture outputs → backend env

```bash
terraform output
```

Map outputs to backend configuration (ECS task environment / Secrets Manager):

| Output | Backend env var |
|--------|-----------------|
| `cognito_user_pool_id` | `COGNITO_USER_POOL_ID` |
| `cognito_client_id` | `COGNITO_CLIENT_ID` |
| `uploads_bucket_name` | `UPLOADS_BUCKET_NAME` |
| `reading_results_bucket_name` | `READING_RESULTS_BUCKET_NAME` |
| `kb_chunk_bucket_name` | `KB_CHUNK_BUCKET_NAME` |
| `jobs_table_name` | `JOBS_TABLE_NAME` |
| `progress_table_name` | `PROGRESS_TABLE_NAME` |
| `conversations_table_name` | `CONVERSATIONS_TABLE_NAME` |
| `jobs_queue_url` | `JOBS_QUEUE_URL` |
| `knowledge_base_id` | `KNOWLEDGE_BASE_ID` |
| (KB data source id) | `KNOWLEDGE_BASE_DATA_SOURCE_ID` |

Set `APP_ENV=prod` (or `dev`) and leave `LOCAL_MOCK`/`AUTH_ALLOW_LOCAL_DEV_USER`
**unset** in deployed environments.

## 3. Build & push images

Five images go to ECR: `api`, `mcp`, `agent-ingestion`, `agent-adaptive`,
`agent-discussion`. In CI this is `build.yml`; manually:

```bash
REGION=eu-central-1
ACCT=$(aws sts get-caller-identity --query Account --output text)
REG=$ACCT.dkr.ecr.$REGION.amazonaws.com
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $REG

# from backend/ as the build context:
cd backend
for pair in \
  "Dockerfile:book-companion-api" \
  "Dockerfile.mcp:book-companion-mcp" \
  "agents/Dockerfile.ingestion:book-companion-agent-ingestion" \
  "agents/Dockerfile.adaptive_reading:book-companion-agent-adaptive" \
  "agents/Dockerfile.discussion:book-companion-agent-discussion"; do
  df="${pair%%:*}"; repo="${pair##*:}"
  docker build -f "$df" -t "$REG/$repo:latest" .
  docker push "$REG/$repo:latest"
done
```

## 4. Deploy the services

- **FastAPI** — **[needs infra]** register the task definition against the ECS
  service and roll it (CI `deploy.yml` does `aws ecs update-service
  --force-new-deployment`). The service runs in private subnets, fronted by the
  ALB over HTTPS.
- **MCP tool server** — runs as its own ECS service (or AgentCore-hosted), with a
  least-privilege role scoped to the KB, buckets, and tables it uses.
- **Agents** — deploy each agent image to its **own AgentCore Runtime**; wire the
  two async agents (ingestion, adaptive-reading) to consume the SQS queue, and
  the discussion agent for direct invoke.

## 5. Ingest the Knowledge Base

The ingestion agent writes prepared chunks to the KB chunk bucket and starts a
Bedrock KB ingestion job (building the Neptune Analytics graph). First upload
through the app triggers this automatically; you can also start an ingestion job
from the Bedrock console to validate the data source.

## 6. Frontend

```bash
cd frontend
VITE_API_BASE_URL=https://<api-host> VITE_AUTH_MODE=cognito npm run build
# upload dist/ to the frontend S3 bucket; serve via CloudFront
```

Wire the real Cognito sign-in flow (the app scaffolds `VITE_AUTH_MODE=cognito`;
the hosted-UI/token exchange is the remaining frontend auth task).

## 7. Validate

```bash
# Obtain a Cognito access token for a test user, then:
python scripts/e2e_smoke.py --base-url https://<api-host> --token "$JWT"
```

Expect all checks to pass (see `docs/e2e-validation.md`).

## 8. CI/CD hand-off

Set the repository variables so GitHub Actions can deploy via OIDC (no static
keys): `AWS_ROLE_ARN`, `ECS_CLUSTER`, `ECS_SERVICE`, and create the GitHub
`production` Environment with required reviewers. See
`.github/workflows/README.md`.

## Teardown

```bash
cd infrastructure/terraform
terraform destroy -var-file=environments/dev/dev.tfvars
```

> **Cost note:** Neptune Analytics and always-on Fargate tasks are the main cost
> drivers. Destroy dev stacks when idle.

## Remaining infra work (to make this fully executable)

1. Implement `modules/networking` (VPC, public/private subnets ≥2 AZs, SGs,
   egress), `modules/ecs` (cluster, Fargate task defs + services for API and MCP,
   execution + least-privilege task roles, autoscaling, `assign_public_ip=false`),
   and `modules/alb` (ALB, HTTPS listener + ACM cert, target group, `/health`).
2. Add the per-agent AgentCore Runtime resources + SQS event wiring in
   `modules/ai`.
3. Add CloudFront + S3 frontend hosting in `modules/storage`.
4. Build the Cognito hosted-UI / token-exchange path in the frontend
   (`VITE_AUTH_MODE=cognito`).
