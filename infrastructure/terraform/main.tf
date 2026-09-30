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

# --- Module composition (enabled incrementally in the infra task group) ---
#
# module "networking" {
#   source      = "./modules/networking"
#   name_prefix = local.name_prefix
# }
#
# module "ecr" {
#   source      = "./modules/ecr"
#   name_prefix = local.name_prefix
# }
#
# module "alb" {
#   source      = "./modules/alb"
#   name_prefix = local.name_prefix
# }
#
# module "ecs" {
#   source      = "./modules/ecs"
#   name_prefix = local.name_prefix
# }
#
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
}
#
module "observability" {
  source      = "./modules/observability"
  name_prefix = local.name_prefix
}
