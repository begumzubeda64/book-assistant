# Deployment Runbook

How to take Book Companion from the repo to a running stack in **`eu-central-1`**.

> **Status note — read first.** The application code (FastAPI, 3 agents, MCP
> server) and the Terraform for **networking, alb, ecs, cognito, storage,
> database (DynamoDB), messaging (SQS), ai (Bedrock KB + Neptune Analytics
> GraphRAG), ecr, and observability** are implemented. Compute (ALB + ECS) is
> **gated on `certificate_arn`**: provision networking/registry/data first, then
> set the cert to bring up the services. Remaining before a fully live stack:
> an ACM certificate + DNS, the per-agent **AgentCore Runtime** resources + SQS
> event wiring, CloudFront/S3 **frontend hosting**, and the Cognito hosted-UI
> auth path in the frontend (all listed at the end).

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

This creates: the VPC (public/private subnets across 2 AZs, IGW, NAT, SGs),
Cognito user pool + client, S3 buckets (uploads, reading results, KB chunks —
all public-access-blocked), DynamoDB tables (jobs, progress, conversations), SQS
job queue + DLQ, the Bedrock Knowledge Base + Neptune Analytics graph, ECR
repositories, and CloudWatch alarms.

### Bring up compute (two-stage)

The ALB and ECS services are gated on `certificate_arn` (so you can provision
the data/registry layers and push images first). Once you have an ACM
certificate and the images are in ECR:

```bash
terraform apply -var-file=environments/dev/dev.tfvars \
  -var 'certificate_arn=arn:aws:acm:eu-central-1:<acct>:certificate/<id>' \
  -var 'image_tag=latest'
```

This adds the ALB (HTTPS + HTTP→HTTPS redirect) and the ECS Fargate services
(API behind the ALB, MCP internal) in **private subnets with no public IPs**,
each with a least-privilege task role, plus API autoscaling. `terraform output
api_url` prints the public endpoint.

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

## Agents, frontend hosting, and Cognito auth

These are implemented and apply as part of the two-stage flow:

- **AgentCore runtimes** — `modules/ai` creates three `awscc_bedrockagentcore_runtime`
  resources (ingestion, adaptive, discussion) with a least-privilege execution
  role, gated on `-var 'deploy_agents=true'` once the agent images are in ECR:
  ```bash
  terraform apply -var-file=environments/dev/dev.tfvars \
    -var 'deploy_agents=true' -var 'image_tag=latest' \
    -var 'certificate_arn=arn:aws:acm:eu-central-1:<acct>:certificate/<id>'
  ```
  SQS → agent delivery: AgentCore runtimes are invoked (not a native SQS event
  source), so the **dispatcher** service (`modules/ecs`, reuses the API image
  with the `src.workflows.dispatcher_main` entrypoint) polls the job queue and
  invokes the matching runtime via `bedrock-agentcore:InvokeAgentRuntime`. It is
  created automatically when `deploy_agents=true` (its task role is scoped to
  SQS receive/delete + agent invoke). Runtime ARNs are in the
  `agent_runtime_arns` output.
- **Frontend hosting** — `modules/storage` provisions a private S3 bucket + a
  CloudFront distribution (OAC, SPA fallback). Build and publish:
  ```bash
  cd frontend
  VITE_API_BASE_URL=https://<api-host> VITE_AUTH_MODE=cognito \
    VITE_COGNITO_DOMAIN=<hosted-ui-domain> VITE_COGNITO_CLIENT_ID=<client> \
    VITE_COGNITO_REDIRECT=https://<frontend-host>/auth/callback npm run build
  aws s3 sync dist/ s3://$(terraform -chdir=../infrastructure/terraform output -raw frontend_bucket_name)/ --delete
  aws cloudfront create-invalidation --distribution-id <id> --paths '/*'
  ```
- **Cognito Hosted UI auth** — the frontend implements the authorization-code +
  PKCE flow (`features/auth/cognito.ts`, `/auth/callback` route). Configure the
  Cognito app client's callback URL (`/auth/callback`) and sign-out URL, and a
  Hosted UI domain.

## Remaining to go fully live

1. An **ACM certificate** (+ DNS/Route 53 alias to the ALB and, if used, a custom
   domain for CloudFront).
2. A **Cognito Hosted UI domain** + app-client callback/logout URLs.
3. Run `terraform apply` (two-stage), push images, publish the frontend, and
   run `scripts/e2e_smoke.py` against the live API.

The SQS→AgentCore bridge is now the **dispatcher** ECS service (see above) — no
longer a manual step.
