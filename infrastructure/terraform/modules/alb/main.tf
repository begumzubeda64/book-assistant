# ALB module.
#
# Internet-facing Application Load Balancer in the public subnets — the only
# public entry point. Two modes:
#   * HTTPS mode (default): a 443 HTTPS listener (ACM cert) with HTTP:80
#     redirecting to it. Used once a domain + certificate are available.
#   * HTTP-only mode (enable_http_only, domain-free demo): a single HTTP:80
#     listener that forwards to the target group, with no cert and no redirect.
#     Browsers reach the API over HTTPS through the CloudFront distribution
#     (enable_api_cdn), which terminates TLS and forwards to the ALB over HTTP.
#
# The target group uses ip targets (Fargate awsvpc) and health-checks /health.

resource "aws_lb" "this" {
  name               = "${var.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids
  tags               = { Name = "${var.name_prefix}-alb" }
}

resource "aws_lb_target_group" "api" {
  name        = "${var.name_prefix}-api-tg"
  port        = var.app_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  tags = { Name = "${var.name_prefix}-api-tg" }
}

# --- HTTPS mode (default) ---

# HTTPS listener forwards to the API target group.
resource "aws_lb_listener" "https" {
  count             = var.enable_http_only ? 0 : 1
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# HTTP redirects to HTTPS.
resource "aws_lb_listener" "http_redirect" {
  count             = var.enable_http_only ? 0 : 1
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# --- HTTP-only mode (domain-free demo) ---

# Single HTTP listener that forwards to the API target group.
resource "aws_lb_listener" "http_forward" {
  count             = var.enable_http_only ? 1 : 0
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# --- API CloudFront distribution (HTTPS on *.cloudfront.net, forwards to ALB) ---
#
# Gives the API a browser-friendly HTTPS URL without a custom domain. Caching is
# effectively disabled (the AWS managed CachingDisabled policy) and all viewer
# headers/methods/query strings are forwarded (AllViewerExceptHostHeader), so
# this behaves as a transparent HTTPS->HTTP proxy to the ALB, suitable for a
# dynamic JSON API. Not a production hardening boundary.
resource "aws_cloudfront_distribution" "api" {
  count   = var.enable_api_cdn ? 1 : 0
  enabled = true
  comment = "${var.name_prefix} API"

  origin {
    domain_name = aws_lb.this.dns_name
    origin_id   = "api-alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "api-alb"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods         = ["GET", "HEAD"]

    # AWS managed policies: CachingDisabled + AllViewerExceptHostHeader.
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  price_class = "PriceClass_100"
}
