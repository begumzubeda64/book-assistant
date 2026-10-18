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
locals {
  # Compute (ALB + ECS) comes up when either a real certificate is supplied
  # (HTTPS mode) or the domain-free HTTP-only demo mode is enabled.
  enable_compute = var.certificate_arn != "" || var.enable_http_only
}

module "alb" {
  count       = local.enable_compute ? 1 : 0
  source      = "./modules/alb"
  name_prefix = local.name_prefix

  vpc_id                = module.networking.vpc_id
  public_subnet_ids     = module.networking.public_subnet_ids
  alb_security_group_id = module.networking.alb_security_group_id
  certificate_arn       = var.certificate_arn
  enable_http_only      = var.enable_http_only
  enable_api_cdn        = var.enable_api_cdn
  app_port              = var.app_port
}

module "ecs" {
  count       = local.enable_compute ? 1 : 0
  source      = "./modules/ecs"
  name_prefix = local.name_prefix

  private_subnet_ids      = module.networking.private_subnet_ids
  tasks_security_group_id = module.networking.tasks_security_group_id
  api_target_group_arn    = module.alb[0].api_target_group_arn
  app_port                = var.app_port

  api_image      = "${module.ecr.repository_urls["api"]}:${var.image_tag}"
  log_group_name = module.observability.app_log_group_name

  dynamodb_table_arns = [
    module.database.jobs_table_arn,
    "${module.database.jobs_table_arn}/index/*",
    module.database.progress_table_arn,
    module.database.conversations_table_arn,
  ]
  # The API only needs the upload + reading-result buckets (presign + read
  # results). Chunk/KB access lives entirely in the MCP tool tier.
  app_bucket_arns = [
    module.storage.uploads_bucket_arn,
    module.storage.reading_results_bucket_arn,
  ]
  jobs_queue_arn           = module.messaging.jobs_queue_arn
  scope_secret_arn         = var.deploy_agents ? module.ai.scope_secret_arn : ""
  enable_agent_integration = var.deploy_agents

  api_environment = {
    APP_ENV              = var.environment
    AWS_REGION           = var.aws_region
    COGNITO_USER_POOL_ID = module.cognito.user_pool_id
    COGNITO_CLIENT_ID    = module.cognito.user_pool_client_id
    # Allow the CloudFront-hosted SPA origin to call the API (browser CORS).
    # pydantic-settings parses list[str] from env as a JSON array.
    CORS_ALLOW_ORIGINS            = jsonencode(["https://${module.storage.frontend_cloudfront_domain}"])
    UPLOADS_BUCKET_NAME           = module.storage.uploads_bucket_name
    READING_RESULTS_BUCKET_NAME   = module.storage.reading_results_bucket_name
    KB_CHUNK_BUCKET_NAME          = module.ai.kb_chunk_bucket_name
    JOBS_TABLE_NAME               = module.database.jobs_table_name
    PROGRESS_TABLE_NAME           = module.database.progress_table_name
    CONVERSATIONS_TABLE_NAME      = module.database.conversations_table_name
    JOBS_QUEUE_URL                = module.messaging.jobs_queue_url
    KNOWLEDGE_BASE_ID             = module.ai.knowledge_base_id
    KNOWLEDGE_BASE_DATA_SOURCE_ID = module.ai.knowledge_base_data_source_id
    # Discussion runs in the agent/MCP tier; the API invokes the discussion
    # runtime and mints the scope token. It holds NO Bedrock permissions.
    AGENT_RUNTIME_ARN_DISCUSSION = try(module.ai.discussion_runtime_arn, "")
    SCOPE_SECRET_ARN             = try(module.ai.scope_secret_arn, "")
  }

  # The API invokes the discussion runtime (chat) and the MCP runtime (book
  # deletion -> KB cleanup). Granted when agents are deployed. No Bedrock data
  # permissions on the API role.
  api_invoke_runtime_arns = var.deploy_agents ? compact([
    module.ai.discussion_runtime_arn,
    module.ai.mcp_runtime_arn,
  ]) : []
  api_secret_arns         = var.deploy_agents ? compact([module.ai.scope_secret_arn]) : []

  # Dispatcher: enabled once agents are deployed (needs their runtime ARNs).
  dispatcher_image       = var.deploy_agents ? "${module.ecr.repository_urls["api"]}:${var.image_tag}" : ""
  agent_runtime_arns     = var.deploy_agents ? values(module.ai.agent_runtime_arns) : ["*"]
  dispatcher_secret_arns = var.deploy_agents ? compact([module.ai.scope_secret_arn]) : []
  dispatcher_environment = {
    APP_ENV                     = var.environment
    AWS_REGION                  = var.aws_region
    JOBS_QUEUE_URL              = module.messaging.jobs_queue_url
    AGENT_RUNTIME_ARN_INGESTION = try(module.ai.agent_runtime_arns["ingestion"], "")
    AGENT_RUNTIME_ARN_ADAPTIVE  = try(module.ai.agent_runtime_arns["adaptive"], "")
    SCOPE_SECRET_ARN            = try(module.ai.scope_secret_arn, "")
  }
}

module "cognito" {
  source      = "./modules/cognito"
  name_prefix = local.name_prefix

  # Hosted-UI login + PKCE callbacks for the deployed CloudFront SPA, so the
  # real browser login flow works without a custom domain.
  hosted_ui_domain_prefix = var.cognito_hosted_ui_domain_prefix
  extra_callback_urls     = ["https://${module.storage.frontend_cloudfront_domain}/auth/callback"]
  extra_logout_urls       = ["https://${module.storage.frontend_cloudfront_domain}"]
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

  # GraphRAG chunk-entity-extraction model (EU inference-profile ARN).
  graph_construction_model_arn = var.graph_construction_model_arn

  # Generation model for the reading/discussion agents (EU inference profile).
  generation_model_id = var.generation_model_id

  # Agent runtimes (two-stage like compute: enable once agent images are pushed).
  deploy_agents = var.deploy_agents
  agent_image_uris = var.deploy_agents ? {
    ingestion  = "${module.ecr.repository_urls["agent-ingestion"]}:${var.image_tag}"
    adaptive   = "${module.ecr.repository_urls["agent-adaptive"]}:${var.image_tag}"
    discussion = "${module.ecr.repository_urls["agent-discussion"]}:${var.image_tag}"
  } : {}
  mcp_image_uri = var.deploy_agents ? "${module.ecr.repository_urls["mcp"]}:${var.image_tag}" : ""

  jobs_queue_arn              = module.messaging.jobs_queue_arn
  uploads_bucket_arn          = module.storage.uploads_bucket_arn
  reading_results_bucket_arn  = module.storage.reading_results_bucket_arn
  jobs_table_arn              = module.database.jobs_table_arn
  conversations_table_arn     = module.database.conversations_table_arn
  uploads_bucket_name         = module.storage.uploads_bucket_name
  reading_results_bucket_name = module.storage.reading_results_bucket_name
  jobs_table_name             = module.database.jobs_table_name
}
#
module "observability" {
  source      = "./modules/observability"
  name_prefix = local.name_prefix
}
