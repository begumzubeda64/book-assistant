# Observability module.
#
# CloudWatch log groups, an application-error metric filter, and alarms for the
# operational signals in tech.md ("Observability"): ECS/ALB health, application
# error rate, and async job failures. Alarm actions notify an SNS topic that
# operators can subscribe to.

resource "aws_cloudwatch_log_group" "app" {
  name              = "/book-companion/${var.name_prefix}/app"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "agents" {
  name              = "/book-companion/${var.name_prefix}/agents"
  retention_in_days = var.log_retention_days
}

# --- Alarm notification topic ---
resource "aws_sns_topic" "alarms" {
  name = "${var.name_prefix}-alarms"
}

# --- Application error rate (from structured JSON logs) ---
resource "aws_cloudwatch_log_metric_filter" "app_errors" {
  name           = "${var.name_prefix}-app-errors"
  log_group_name = aws_cloudwatch_log_group.app.name
  # Structured logs use {"level":"ERROR",...}; count ERROR-level lines.
  pattern = "{ $.level = \"ERROR\" }"

  metric_transformation {
    name          = "AppErrors"
    namespace     = "BookCompanion/${var.name_prefix}"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "app_error_rate" {
  alarm_name          = "${var.name_prefix}-app-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = aws_cloudwatch_log_metric_filter.app_errors.metric_transformation[0].name
  namespace           = "BookCompanion/${var.name_prefix}"
  period              = 300
  statistic           = "Sum"
  threshold           = var.app_error_threshold
  treat_missing_data  = "notBreaching"
  alarm_description   = "Elevated application error rate."
  alarm_actions       = [aws_sns_topic.alarms.arn]
}

# --- ALB 5xx (target-side errors) ---
resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  count = var.alb_arn_suffix == "" ? 0 : 1

  alarm_name          = "${var.name_prefix}-alb-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = var.alb_5xx_threshold
  treat_missing_data  = "notBreaching"
  alarm_description   = "Elevated ALB target 5xx responses."
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }
}

# --- Async job failures (from the job-failure metric emitted by the app) ---
resource "aws_cloudwatch_log_metric_filter" "job_failures" {
  name           = "${var.name_prefix}-job-failures"
  log_group_name = aws_cloudwatch_log_group.agents.name
  pattern        = "{ $.message = \"*_failed\" }"

  metric_transformation {
    name          = "JobFailures"
    namespace     = "BookCompanion/${var.name_prefix}"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "job_failures" {
  alarm_name          = "${var.name_prefix}-job-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = aws_cloudwatch_log_metric_filter.job_failures.metric_transformation[0].name
  namespace           = "BookCompanion/${var.name_prefix}"
  period              = 300
  statistic           = "Sum"
  threshold           = var.job_failure_threshold
  treat_missing_data  = "notBreaching"
  alarm_description   = "Async job failures detected."
  alarm_actions       = [aws_sns_topic.alarms.arn]
}
