output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "mcp_service_name" {
  value = aws_ecs_service.mcp.name
}

output "api_task_role_arn" {
  value = aws_iam_role.api_task.arn
}
