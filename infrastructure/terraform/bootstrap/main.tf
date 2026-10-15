# Terraform state backend bootstrap (one-time, run before the main stack).
#
# Creates the S3 bucket + DynamoDB lock table that the main configuration uses
# as its remote backend. This must exist first (the backend can't create its own
# bucket), so it is a separate root with LOCAL state of its own — that's
# expected and fine for a one-time bootstrap.
#
#   cd infrastructure/terraform/bootstrap
#   terraform init
#   terraform apply -var-file=../environments/dev/dev.tfvars
#
# Then configure the main stack's backend (see ../backend.tf) and run
# `terraform init` in ../ to migrate state.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.90"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Component = "tfstate-bootstrap"
    }
  }
}

locals {
  state_bucket = "${var.project}-${var.environment}-tfstate"
  lock_table   = "${var.project}-${var.environment}-tflock"
}

resource "aws_s3_bucket" "state" {
  bucket = local.state_bucket
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "lock" {
  name         = local.lock_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"
  attribute {
    name = "LockID"
    type = "S"
  }
}

variable "aws_region" {
  type    = string
  default = "eu-central-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "project" {
  type    = string
  default = "book-companion"
}

output "state_bucket" {
  value = aws_s3_bucket.state.id
}

output "lock_table" {
  value = aws_dynamodb_table.lock.name
}
