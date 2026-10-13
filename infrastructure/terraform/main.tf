# Root Terraform configuration for Book Companion.
#
# Milestone 1: module SKELETON only. Modules exist as empty, documented
# placeholders; real resources are added in the infrastructure task group
# (spec tasks.md group 3 and the AI/AgentCore group). The root wires the AWS
# provider (region fixed to eu-central-1) and default tags. Module calls are
# declared but commented until each module defines real resources, so the
# skeleton passes `terraform validate`.

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  name_prefix = "${var.project}-${var.environment}"
}

# --- Networking + registry (always provisioned) ---
module "networking" {
  source      = "./modules/networking"
  name_prefix = local.name_prefix
  app_port    = var.app_port
}

module "ecr" {
  source      = "./modules/ecr"
  name_prefix = local.name_prefix
}

# --- Load balancer + compute (require an ACM certificate) ---
# Provision networking/ecr/data layers first; set certificate_arn (and push the
# images) to bring up the ALB + ECS services.
module "alb" {
  count       = var.certificate_arn == "" ? 0 : 1
  source      = "./modules/alb"
  name_prefix = local.name_prefix

  vpc_id                = module.networking.vpc_id
  public_subnet_ids     = module.networking.public_subnet_ids
  alb_security_group_id = module.networking.alb_security_group_id
  certificate_arn       = var.certificate_arn
  app_port              = var.app_port
}

module "ecs" {
  count       = var.certificate_arn == "" ? 0 : 1
  source      = "./modules/ecs"
  name_prefix = local.name_prefix

  private_subnet_ids      = module.networking.private_subnet_ids
  tasks_security_group_id = module.networking.tasks_security_group_id
  api_target_group_arn    = module.alb[0].api_target_group_arn
  app_port                = var.app_port

  api_image      = "${module.ecr.repository_urls["api"]}:${var.image_tag}"
  mcp_image      = "${module.ecr.repository_urls["mcp"]}:${var.image_tag}"
  log_group_name = module.observability.app_log_group_name

  dynamodb_table_arns = [
    module.database.jobs_table_arn,
    "${module.database.jobs_table_arn}/index/*",
    module.database.progress_table_arn,
    module.database.conversations_table_arn,
  ]
  app_bucket_arns = [
    module.storage.uploads_bucket_arn,
    module.storage.reading_results_bucket_arn,
    module.ai.kb_chunk_bucket_arn,
  ]
  jobs_queue_arn = module.messaging.jobs_queue_arn

  api_environment = {
    APP_ENV                       = var.environment
    AWS_REGION                    = var.aws_region
    COGNITO_USER_POOL_ID          = module.cognito.user_pool_id
    COGNITO_CLIENT_ID             = module.cognito.user_pool_client_id
    UPLOADS_BUCKET_NAME           = module.storage.uploads_bucket_name
    READING_RESULTS_BUCKET_NAME   = module.storage.reading_results_bucket_name
    KB_CHUNK_BUCKET_NAME          = module.ai.kb_chunk_bucket_name
    JOBS_TABLE_NAME               = module.database.jobs_table_name
    PROGRESS_TABLE_NAME           = module.database.progress_table_name
    CONVERSATIONS_TABLE_NAME      = module.database.conversations_table_name
    JOBS_QUEUE_URL                = module.messaging.jobs_queue_url
    KNOWLEDGE_BASE_ID             = module.ai.knowledge_base_id
    KNOWLEDGE_BASE_DATA_SOURCE_ID = module.ai.knowledge_base_data_source_id
  }
}

module "cognito" {
  source      = "./modules/cognito"
  name_prefix = local.name_prefix
}
#
module "storage" {
  source      = "./modules/storage"
  name_prefix = local.name_prefix
}
#
module "database" {
  source      = "./modules/database"
  name_prefix = local.name_prefix
}
#
module "messaging" {
  source      = "./modules/messaging"
  name_prefix = local.name_prefix
}
#
module "ai" {
  source      = "./modules/ai"
  name_prefix = local.name_prefix
  environment = var.environment

  # Agent runtimes (two-stage like compute: enable once agent images are pushed).
  deploy_agents = var.deploy_agents
  agent_image_uris = var.deploy_agents ? {
    ingestion  = "${module.ecr.repository_urls["agent-ingestion"]}:${var.image_tag}"
    adaptive   = "${module.ecr.repository_urls["agent-adaptive"]}:${var.image_tag}"
    discussion = "${module.ecr.repository_urls["agent-discussion"]}:${var.image_tag}"
  } : {}

  jobs_queue_arn             = module.messaging.jobs_queue_arn
  uploads_bucket_arn         = module.storage.uploads_bucket_arn
  reading_results_bucket_arn = module.storage.reading_results_bucket_arn
  jobs_table_arn             = module.database.jobs_table_arn
  conversations_table_arn    = module.database.conversations_table_arn
}
#
module "observability" {
  source      = "./modules/observability"
  name_prefix = local.name_prefix
}
