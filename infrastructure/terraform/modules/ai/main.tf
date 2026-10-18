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

locals {
  # GraphRAG entity extraction (contextEnrichmentConfiguration) must reference a
  # model that is actually invokable in this Region AND accepted for graph
  # construction. In eu-central-1 the Anthropic Claude models are only reachable
  # through an EU cross-Region inference profile (ARN prefix "eu."), not a bare
  # foundation-model ARN, and GraphRAG only accepts Claude Haiku-family models
  # for this step (Sonnet is rejected with "Invalid graph bedrock foundation
  # model provided"). This is therefore a required, explicitly supplied profile
  # ARN rather than something derived from the generation model.
  graph_construction_model_arn = var.graph_construction_model_arn

  # Underlying foundation-model id behind the graph-construction inference
  # profile, e.g. "eu.anthropic.claude-haiku-4-5-20251001-v1:0" ->
  # "anthropic.claude-haiku-4-5-20251001-v1:0". Used to grant the KB role
  # InvokeModel on the foundation model the profile routes to.
  graph_construction_profile_id = element(split("/", local.graph_construction_model_arn), 1)
  graph_construction_model_id   = replace(local.graph_construction_profile_id, "/^(eu|us|apac|global)[.]/", "")

  # Underlying foundation-model id behind the generation inference profile,
  # used to grant the MCP role InvokeModel on the model the profile routes to.
  generation_model_base_id = replace(var.generation_model_id, "/^(eu|us|apac|global)[.]/", "")

  # Baseline permissions every AgentCore runtime execution role needs to start
  # and operate: pull its image from ECR, write logs + traces, emit metrics, and
  # mint workload-access tokens. (Per the AWS AgentCore Terraform sample.)
  agentcore_baseline_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EcrImagePull"
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchCheckLayerAvailability",
        ]
        Resource = "arn:aws:ecr:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:repository/${var.name_prefix}-*"
      },
      {
        Sid      = "EcrAuthToken"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
      },
      {
        Sid    = "XRayTracing"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets",
        ]
        Resource = "*"
      },
      {
        Sid      = "CloudWatchMetrics"
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
        Condition = {
          StringEquals = { "cloudwatch:namespace" = "bedrock-agentcore" }
        }
      },
      {
        Sid    = "WorkloadAccessTokens"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:GetWorkloadAccessToken",
          "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
          "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
        ]
        Resource = [
          "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default",
          "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:workload-identity-directory/default/workload-identity/*",
        ]
      },
    ]
  })
}

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
        # Embedding model (vectors) + the graph-construction model (GraphRAG
        # chunk entity extraction during ingestion) are invoked under this role.
        # (The generation model is invoked by the agents, not by the KB role.)
        # The graph-construction model is an EU cross-Region inference profile,
        # so per the Bedrock inference-profile prerequisites the role must be
        # granted BOTH the inference-profile ARN AND the underlying foundation-
        # model ARN in every destination Region the profile routes to — scoped
        # here with a Region wildcard on the foundation-model ARN. The underlying
        # model id is derived from the profile ARN by stripping the "eu." prefix.
        Effect = "Allow"
        Action = ["bedrock:InvokeModel"]
        Resource = [
          var.embedding_model_arn,
          local.graph_construction_model_arn,
          "arn:aws:bedrock:*::foundation-model/${local.graph_construction_model_id}",
        ]
      },
      {
        # The graph-construction model is a cross-Region inference profile, which
        # the KB validates at data-source creation by calling GetInferenceProfile
        # on the profile ARN. Without this the create fails with "Not authorized
        # to call GetInferenceProfile".
        # GetInferenceProfile does not support resource-level scoping to a single
        # profile ARN; an ARN-scoped grant matches nothing and the call is denied
        # ("Not authorized to call GetInferenceProfile"). It must be "*". This is
        # a read-only describe action (metadata only, no data/inference access).
        Sid      = "InferenceProfileDescribe"
        Effect   = "Allow"
        Action   = ["bedrock:GetInferenceProfile"]
        Resource = "*"
      },
      {
        # Explicit Neptune Analytics actions GraphRAG requires (per the Bedrock
        # KB "vector database in Amazon Neptune Analytics" permissions doc).
        # GetGraph is checked during KB creation; the query actions are used for
        # graph read/write/delete during ingestion and retrieval.
        Sid    = "NeptuneAnalyticsGraphAccess"
        Effect = "Allow"
        Action = [
          "neptune-graph:GetGraph",
          "neptune-graph:ReadDataViaQuery",
          "neptune-graph:WriteDataViaQuery",
          "neptune-graph:DeleteDataViaQuery",
        ]
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

  # Required for Neptune Analytics (GraphRAG): a Bedrock foundation model
  # performs chunk entity extraction to build the graph during ingestion.
  # In the awscc provider this nests under vector_ingestion_configuration.
  vector_ingestion_configuration = {
    context_enrichment_configuration = {
      type = "BEDROCK_FOUNDATION_MODEL"
      bedrock_foundation_model_configuration = {
        # Entity extraction is generative → use the graph-construction model,
        # resolved to an EU inference-profile ARN (see locals above).
        model_arn = local.graph_construction_model_arn
        enrichment_strategy_configuration = {
          method = "CHUNK_ENTITY_EXTRACTION"
        }
      }
    }
  }
}

# --- Agent + tool tier: AgentCore runtimes ---
#
# Created when deploy_agents=true and the images exist in ECR (two-stage, like
# the ALB/ECS compute). Architecture (decisions.md, security.md):
#   * Three ISOLATED agent runtimes (ingestion, adaptive, discussion), each its
#     own image, deploying/scaling/failing independently.
#   * One MCP tool-server runtime holding ALL AWS data permissions. Agents hold
#     none; they reach tools only via InvokeAgentRuntime on the MCP runtime.
#   * A per-job scope secret (Secrets Manager) signs the trusted user_id so a
#     compromised agent cannot act as another user. Only the MCP server and the
#     dispatcher/API read it.

locals {
  agents = var.deploy_agents ? {
    ingestion  = try(var.agent_image_uris["ingestion"], "")
    adaptive   = try(var.agent_image_uris["adaptive"], "")
    discussion = try(var.agent_image_uris["discussion"], "")
  } : {}
}

# --- Scope-signing secret (Secrets Manager) ---
resource "aws_secretsmanager_secret" "scope" {
  count                   = var.deploy_agents ? 1 : 0
  name                    = "${var.name_prefix}-scope-signing-secret"
  recovery_window_in_days = 0
}

resource "random_password" "scope" {
  count   = var.deploy_agents ? 1 : 0
  length  = 48
  special = false
}

resource "aws_secretsmanager_secret_version" "scope" {
  count         = var.deploy_agents ? 1 : 0
  secret_id     = aws_secretsmanager_secret.scope[0].id
  secret_string = random_password.scope[0].result
}

# --- MCP tool-server execution role: the ONLY role with data permissions ---
resource "aws_iam_role" "mcp_exec" {
  count = var.deploy_agents ? 1 : 0
  name  = "${var.name_prefix}-mcp-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnLike = {
          "aws:SourceArn" = "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
        }
      }
    }]
  })
}

# Baseline permissions every AgentCore runtime needs to start and run: pull its
# image from ECR, write logs/traces, and mint workload-access tokens.
resource "aws_iam_role_policy" "mcp_exec_baseline" {
  count  = var.deploy_agents ? 1 : 0
  name   = "${var.name_prefix}-mcp-exec-baseline"
  role   = aws_iam_role.mcp_exec[0].id
  policy = local.agentcore_baseline_policy
}

resource "aws_iam_role_policy" "mcp_exec" {
  count = var.deploy_agents ? 1 : 0
  name  = "${var.name_prefix}-mcp-exec-policy"
  role  = aws_iam_role.mcp_exec[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Bedrock"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel", "bedrock:Retrieve", "bedrock:StartIngestionJob"]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/${local.graph_construction_model_id}",
          "arn:aws:bedrock:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:inference-profile/${var.generation_model_id}",
          "arn:aws:bedrock:*::foundation-model/${local.generation_model_base_id}",
          awscc_bedrock_knowledge_base.graphrag.knowledge_base_arn,
        ]
      },
      {
        Sid      = "InferenceProfileDescribe"
        Effect   = "Allow"
        Action   = ["bedrock:GetInferenceProfile"]
        Resource = "*"
      },
      {
        Sid    = "ContentChunkAndResultBuckets"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = compact([
          aws_s3_bucket.kb_chunks.arn, "${aws_s3_bucket.kb_chunks.arn}/*",
          var.uploads_bucket_arn, var.uploads_bucket_arn == "" ? "" : "${var.uploads_bucket_arn}/*",
          var.reading_results_bucket_arn, var.reading_results_bucket_arn == "" ? "" : "${var.reading_results_bucket_arn}/*",
        ])
      },
      {
        Sid      = "ReadScopeSecret"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.scope[0].arn]
      }
    ]
  })
}

resource "awscc_bedrockagentcore_runtime" "mcp" {
  count = var.deploy_agents && try(var.mcp_image_uri, "") != "" ? 1 : 0

  agent_runtime_name     = replace("${var.name_prefix}-mcp", "-", "_")
  role_arn               = aws_iam_role.mcp_exec[0].arn
  protocol_configuration = "MCP"

  agent_runtime_artifact = {
    container_configuration = {
      container_uri = var.mcp_image_uri
    }
  }

  network_configuration = {
    network_mode = "PUBLIC"
  }

  environment_variables = {
    APP_ENV                       = var.environment
    AWS_REGION                    = data.aws_region.current.name
    KNOWLEDGE_BASE_ID             = awscc_bedrock_knowledge_base.graphrag.knowledge_base_id
    KNOWLEDGE_BASE_DATA_SOURCE_ID = awscc_bedrock_data_source.chunks.data_source_id
    KB_CHUNK_BUCKET_NAME          = aws_s3_bucket.kb_chunks.id
    UPLOADS_BUCKET_NAME           = var.uploads_bucket_name
    READING_RESULTS_BUCKET_NAME   = var.reading_results_bucket_name
    GENERATION_MODEL_ID           = var.generation_model_id
    SCOPE_SIGNING_SECRET          = aws_secretsmanager_secret_version.scope[0].secret_string
  }
}

resource "aws_iam_role" "agent_exec" {
  count = var.deploy_agents ? 1 : 0
  name  = "${var.name_prefix}-agent-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnLike = {
          "aws:SourceArn" = "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
        }
      }
    }]
  })
}

# Baseline AgentCore permissions (ECR pull, logs/traces, workload tokens).
resource "aws_iam_role_policy" "agent_exec_baseline" {
  count  = var.deploy_agents ? 1 : 0
  name   = "${var.name_prefix}-agent-exec-baseline"
  role   = aws_iam_role.agent_exec[0].id
  policy = local.agentcore_baseline_policy
}

resource "aws_iam_role_policy" "agent_exec" {
  count = var.deploy_agents ? 1 : 0
  name  = "${var.name_prefix}-agent-exec-policy"
  role  = aws_iam_role.agent_exec[0].id

  # Least privilege: the agents hold NO direct S3/Bedrock/KB permissions. All
  # content, retrieval, generation, and KB access happens through the MCP tool
  # server, which the agents may only reach via InvokeAgentRuntime. The agents
  # keep just their own job-status bookkeeping on the jobs table.
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "InvokeMcpToolServer"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:InvokeAgentRuntime"]
        Resource = ["${awscc_bedrockagentcore_runtime.mcp[0].agent_runtime_arn}*"]
      },
      {
        Sid      = "JobStatusBookkeeping"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
        Resource = compact([var.jobs_table_arn])
      }
    ]
  })
}

resource "awscc_bedrockagentcore_runtime" "agent" {
  for_each = local.agents

  agent_runtime_name = replace("${var.name_prefix}-${each.key}", "-", "_")
  role_arn           = aws_iam_role.agent_exec[0].arn

  agent_runtime_artifact = {
    container_configuration = {
      container_uri = each.value
    }
  }

  network_configuration = {
    network_mode = "PUBLIC"
  }

  environment_variables = {
    APP_ENV              = var.environment
    AWS_REGION           = data.aws_region.current.name
    JOBS_TABLE_NAME      = var.jobs_table_name
    MCP_RUNTIME_ARN      = try(awscc_bedrockagentcore_runtime.mcp[0].agent_runtime_arn, "")
    SCOPE_SIGNING_SECRET = aws_secretsmanager_secret_version.scope[0].secret_string
  }

  depends_on = [awscc_bedrockagentcore_runtime.mcp]
}
