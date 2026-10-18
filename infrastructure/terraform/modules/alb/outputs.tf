output "alb_dns_name" {
  description = "Public DNS name of the ALB."
  value       = aws_lb.this.dns_name
}

output "alb_zone_id" {
  description = "ALB hosted zone id (for Route 53 alias records)."
  value       = aws_lb.this.zone_id
}

output "api_target_group_arn" {
  description = "Target group the API service registers with."
  value       = aws_lb_target_group.api.arn
}

output "https_listener_arn" {
  description = "HTTPS listener ARN (null in HTTP-only mode)."
  value       = try(aws_lb_listener.https[0].arn, null)
}

output "api_cdn_domain" {
  description = "CloudFront domain for the API (null unless enable_api_cdn)."
  value       = try(aws_cloudfront_distribution.api[0].domain_name, null)
}

# Browser-facing base URL for the API. Prefers the CloudFront HTTPS URL; falls
# back to the ALB HTTPS DNS in HTTPS mode.
output "api_base_url" {
  description = "Public HTTPS base URL for the API."
  value = (
    var.enable_api_cdn
    ? "https://${aws_cloudfront_distribution.api[0].domain_name}"
    : "https://${aws_lb.this.dns_name}"
  )
}
