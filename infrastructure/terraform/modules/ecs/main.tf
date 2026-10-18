# ECS module.
#
# Fargate cluster running the FastAPI service (behind the ALB) and the MCP tool
# server (internal). Tasks run in private subnets with no public IPs. The task
# execution role pulls images + writes logs; each service gets its own
# least-privilege task role scoped to only the AWS resources it uses.

data "aws_region" "current" {}

resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-cluster"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# --- Execution role (shared): pull from ECR + write logs ---
resource "aws_iam_role" "execution" {
  name = "${var.name_prefix}-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow the execution role to resolve the scope secret for container `secrets`
# injection (API + dispatcher). Scoped to the one secret.
resource "aws_iam_role_policy" "execution_secrets" {
  count = var.enable_agent_integration ? 1 : 0
  name  = "${var.name_prefix}-ecs-execution-secrets"
  role  = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [var.scope_secret_arn]
    }]
  })
}

# --- API task role: least privilege for the application tier ---
resource "aws_iam_role" "api_task" {
  name = "${var.name_prefix}-api-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "api_task" {
  name = "${var.name_prefix}-api-task-policy"
  role = aws_iam_role.api_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Dynamo"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
          "dynamodb:Query", "dynamodb:DeleteItem"
        ]
        Resource = var.dynamodb_table_arns
      },
      {
        Sid      = "S3Uploads"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = [for b in var.app_bucket_arns : "${b}/*"]
      },
      {
        Sid      = "Sqs"
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = var.jobs_queue_arn == "" ? ["*"] : [var.jobs_queue_arn]
      }
    ]
  })
}

# API invokes the discussion AgentCore runtime (discussion runs in the agent/MCP
# tier, not the API). Granted only when there are runtime ARNs to invoke.
resource "aws_iam_role_policy" "api_invoke_runtimes" {
  count = var.enable_agent_integration ? 1 : 0
  name  = "${var.name_prefix}-api-invoke-runtimes"
  role  = aws_iam_role.api_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "InvokeDiscussionRuntime"
      Effect   = "Allow"
      Action   = ["bedrock-agentcore:InvokeAgentRuntime"]
      Resource = [for a in var.api_invoke_runtime_arns : "${a}*"]
    }]
  })
}

# Read the scope-signing secret (API mints discussion scope tokens).
resource "aws_iam_role_policy" "api_secrets" {
  count = var.enable_agent_integration ? 1 : 0
  name  = "${var.name_prefix}-api-secrets"
  role  = aws_iam_role.api_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = var.api_secret_arns
    }]
  })
}

# Dispatcher reads the scope-signing secret to mint per-job tokens.
resource "aws_iam_role_policy" "dispatcher_secrets" {
  count = var.enable_agent_integration ? 1 : 0
  name  = "${var.name_prefix}-dispatcher-secrets"
  role  = aws_iam_role.dispatcher_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = var.dispatcher_secret_arns
    }]
  })
}

# NOTE: The MCP tool server runs as its own AgentCore runtime (see the ai
# module), NOT as an ECS task. All Bedrock/KB/data permissions live on the MCP
# runtime's execution role there; the API task role below holds none.

# --- Task definitions ---
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.api_task.arn

  # Images are built arm64 (AgentCore requires arm64; we use one arch across the
  # stack). Fargate must be told to run on Graviton or it defaults to X86_64 and
  # the task fails to start.
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name         = "api"
      image        = var.api_image
      essential    = true
      portMappings = [{ containerPort = var.app_port, protocol = "tcp" }]
      environment  = [for k, v in var.api_environment : { name = k, value = v }]
      # Inject the scope-signing secret from Secrets Manager (never plaintext).
      secrets = var.scope_secret_arn == "" ? [] : [
        { name = "SCOPE_SIGNING_SECRET", valueFrom = var.scope_secret_arn }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.log_group_name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])
}

# --- Services ---
resource "aws_ecs_service" "api" {
  name            = "${var.name_prefix}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.tasks_security_group_id]
    assign_public_ip = false # tasks are private
  }

  load_balancer {
    target_group_arn = var.api_target_group_arn
    container_name   = "api"
    container_port   = var.app_port
  }

  depends_on = [aws_iam_role_policy.api_task]
}

# --- Dispatcher: SQS -> AgentCore bridge (own tier, no ALB) ---
resource "aws_iam_role" "dispatcher_task" {
  name = "${var.name_prefix}-dispatcher-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "dispatcher_task" {
  name = "${var.name_prefix}-dispatcher-task-policy"
  role = aws_iam_role.dispatcher_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ConsumeJobQueue"
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = var.jobs_queue_arn == "" ? ["*"] : [var.jobs_queue_arn]
      },
      {
        Sid      = "InvokeAgents"
        Effect   = "Allow"
        Action   = ["bedrock-agentcore:InvokeAgentRuntime"]
        Resource = var.agent_runtime_arns
      }
    ]
  })
}

resource "aws_ecs_task_definition" "dispatcher" {
  family                   = "${var.name_prefix}-dispatcher"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.dispatcher_task.arn

  # Reuses the arm64 API image -> must run on Graviton Fargate.
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "dispatcher"
      image     = var.dispatcher_image
      essential = true
      # Reuse the API image; run the dispatcher entrypoint instead of the server.
      command     = ["python", "-m", "src.workflows.dispatcher_main"]
      environment = [for k, v in var.dispatcher_environment : { name = k, value = v }]
      secrets = var.scope_secret_arn == "" ? [] : [
        { name = "SCOPE_SIGNING_SECRET", valueFrom = var.scope_secret_arn }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.log_group_name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "dispatcher"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "dispatcher" {
  count           = var.dispatcher_image == "" ? 0 : 1
  name            = "${var.name_prefix}-dispatcher"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.dispatcher.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.tasks_security_group_id]
    assign_public_ip = false
  }

  depends_on = [aws_iam_role_policy.dispatcher_task]
}

# --- API service autoscaling (CPU target tracking) ---
resource "aws_appautoscaling_target" "api" {
  max_capacity       = var.api_max_count
  min_capacity       = var.api_desired_count
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${var.name_prefix}-api-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 65
  }
}
