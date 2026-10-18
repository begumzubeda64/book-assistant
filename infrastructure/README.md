# Infrastructure

All infrastructure is owned by Terraform (region fixed to `eu-central-1`).

## Layout

```
terraform/
  versions.tf        Terraform + provider version constraints
  variables.tf       Root input variables
  main.tf            Provider + module composition
  outputs.tf         Root outputs
  modules/           Reusable modules (see below)
  environments/      Per-environment variable files (dev, prod)
```

### Modules

| Module | Responsibility |
|--------|----------------|
| networking | VPC, subnets (public ALB / private ECS), security groups, egress |
| ecr | ECR repositories (FastAPI image + agent image) |
| alb | Application Load Balancer, HTTPS listener, target group |
| ecs | ECS cluster, Fargate task/service, roles, auto scaling |
| cognito | Cognito User Pool + app client |
| storage | Private S3 (PDFs/results) + CloudFront/S3 frontend hosting |
| database | DynamoDB tables (state + jobs) |
| messaging | SQS queue(s) + DLQ for async job triggering |
| ai | Bedrock Knowledge Base + Neptune Analytics + AgentCore Runtime |
| observability | CloudWatch log groups, metrics, alarms |

## Status

Milestone 1: **skeleton only**. Modules are documented placeholders with no
real resources; module calls in `main.tf` are commented until each module is
implemented in the infrastructure task group. The skeleton is kept
`fmt`/`validate` clean.

## Usage (once resources exist)

```bash
cd terraform
terraform init
terraform fmt -check -recursive
terraform validate
terraform plan  -var-file=environments/dev/dev.tfvars
terraform apply -var-file=environments/dev/dev.tfvars
```
