# CI/CD Workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `ci.yml` | push / PR to `main`, `dev` | Backend ruff + mypy + pytest, frontend lint + build, terraform fmt + validate. No AWS. |
| `build.yml` | push to `main`, `v*` tags, manual | Build the 5 images, Trivy scan (fail on HIGH/CRITICAL), push to ECR via OIDC. |
| `deploy.yml` | manual (choose `dev`/`prod`) | Terraform plan + ECS rolling deploy per environment; `prod` gated by the GitHub `production` Environment. |

## Images built

`api`, `mcp`, `agent-ingestion`, `agent-adaptive`, `agent-discussion` — matching
the isolated-agent + MCP architecture (see `docs/decisions.md`).

## AWS authentication

AWS access uses **OIDC** (no long-lived keys). All AWS steps are gated on the
`AWS_ROLE_ARN` repository variable, so `ci.yml` and the build/scan stages run
green before AWS exists; AWS actions activate once the variable is set.

## Required repository configuration

Set these once AWS is provisioned (Settings → Secrets and variables → Actions →
Variables):

| Variable | Purpose |
|----------|---------|
| `AWS_ROLE_ARN` | IAM role for GitHub OIDC to assume |
| `ECS_CLUSTER` | ECS cluster name (deploy) |
| `ECS_SERVICE` | ECS service name (deploy) |

Region is fixed to `eu-central-1`.

## Production approval gate

Create a GitHub **Environment** named `production` (Settings → Environments)
with **Required reviewers**. The `deploy` job references
`environment: prod`/`dev`; the approval prompt is enforced by the Environment's
protection rules, not by the workflow YAML.

## Notes

- Action versions are pinned to major tags; Dependabot (`.github/dependabot.yml`)
  keeps them and the app dependencies current.
- Trivy uses `ignore-unfixed: true` so only actionable HIGH/CRITICAL findings
  fail the build.
