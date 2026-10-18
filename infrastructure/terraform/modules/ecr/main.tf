# ECR module.
#
# One repository per deployable image (API, MCP tool server, and the three
# isolated agents), with scan-on-push and a lifecycle policy that expires
# untagged images. The three agent repos are separate because the agents are
# isolated images (see decisions.md).

locals {
  repos = [
    "api",
    "mcp",
    "agent-ingestion",
    "agent-adaptive",
    "agent-discussion",
  ]
}

resource "aws_ecr_repository" "this" {
  for_each             = toset(local.repos)
  name                 = "${var.name_prefix}-${each.value}"
  image_tag_mutability = "MUTABLE"
  force_delete         = var.force_delete

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "expire_untagged" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images after 14 days"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 14
      }
      action = { type = "expire" }
    }]
  })
}
