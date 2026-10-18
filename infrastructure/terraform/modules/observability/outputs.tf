output "app_log_group_name" {
  description = "Application CloudWatch log group."
  value       = aws_cloudwatch_log_group.app.name
}

output "agents_log_group_name" {
  description = "Agents CloudWatch log group."
  value       = aws_cloudwatch_log_group.agents.name
}

output "alarms_topic_arn" {
  description = "SNS topic ARN for alarm notifications."
  value       = aws_sns_topic.alarms.arn
}
