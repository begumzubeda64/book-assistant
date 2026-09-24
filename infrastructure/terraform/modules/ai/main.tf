# AI module.
#
# GraphRAG storage + retrieval for the MVP: a Neptune Analytics graph as the
# Bedrock Knowledge Base graph store, an S3 data source for prepared chunks, and
# the Knowledge Base itself. The three AgentCore Runtimes (one per isolated
# agent) and the MCP tool-server hosting are wired in the deployment/agent task
# groups; this module provisions the GraphRAG data plane they depend on.
#
# Region is eu-central-1 (a supported region for Bedrock KB GraphRAG with
# Neptune Analytics). Confirm model IDs are available in-region when selecting
# embedding/generation models.

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# --- Prepared-chunk store (ingested content, ownership-scoped by key prefix) ---
resource "aws_s3_bucket" "kb_chunks" {
  bucket = "${var.name_prefix}-kb-chunks"
}

resource "aws_s3_bucket_public_access_block" "kb_chunks" {
  bucket                  = aws_s3_bucket.kb_chunks.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- Neptune Analytics graph (GraphRAG knowledge representation) ---
resource "aws_neptunegraph_graph" "graphrag" {
  graph_name          = replace("${var.name_prefix}-graphrag", "_", "-")
  provisioned_memory  = var.neptune_memory_ncu
  deletion_protection = var.deletion_protection

  vector_search_configuration {
    vector_search_dimension = var.embedding_dimension
  }
}

# --- IAM role assumed by the Bedrock Knowledge Base ---
resource "aws_iam_role" "kb_role" {
  name = "${var.name_prefix}-kb-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })
}

resource "aws_iam_role_policy" "kb_policy" {
  name = "${var.name_prefix}-kb-policy"
  role = aws_iam_role.kb_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.kb_chunks.arn, "${aws_s3_bucket.kb_chunks.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = var.embedding_model_arn
      },
      {
        Effect   = "Allow"
        Action   = ["neptune-graph:*"]
        Resource = aws_neptunegraph_graph.graphrag.arn
      }
    ]
  })
}

# --- Bedrock Knowledge Base backed by the Neptune Analytics graph ---
#
# Uses the awscc provider: the classic aws provider does not yet support the
# NEPTUNE_ANALYTICS storage type for Bedrock Knowledge Bases (hashicorp/
# terraform-provider-aws#41745), so GraphRAG-with-Neptune is expressed via
# Cloud Control. See decisions.md.
resource "awscc_bedrock_knowledge_base" "graphrag" {
  name     = "${var.name_prefix}-kb"
  role_arn = aws_iam_role.kb_role.arn

  knowledge_base_configuration = {
    type = "VECTOR"
    vector_knowledge_base_configuration = {
      embedding_model_arn = var.embedding_model_arn
    }
  }

  storage_configuration = {
    type = "NEPTUNE_ANALYTICS"
    neptune_analytics_configuration = {
      graph_arn = aws_neptunegraph_graph.graphrag.arn
      field_mapping = {
        text_field     = "text"
        metadata_field = "metadata"
      }
    }
  }

  depends_on = [aws_iam_role_policy.kb_policy]
}

resource "awscc_bedrock_data_source" "chunks" {
  name              = "${var.name_prefix}-kb-chunks"
  knowledge_base_id = awscc_bedrock_knowledge_base.graphrag.knowledge_base_id

  data_source_configuration = {
    type = "S3"
    s3_configuration = {
      bucket_arn = aws_s3_bucket.kb_chunks.arn
    }
  }
}
