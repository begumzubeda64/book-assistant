# Cognito module.
#
# Provisions the Cognito User Pool and app client used for authentication. The
# backend validates JWTs issued by this pool and derives the trusted user_id.

data "aws_region" "current" {}

resource "aws_cognito_user_pool" "this" {
  name = "${var.name_prefix}-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # Do not weaken: keep MFA configurable rather than off in production hardening.
  mfa_configuration = "OPTIONAL"

  software_token_mfa_configuration {
    enabled = true
  }

  admin_create_user_config {
    allow_admin_create_user_only = false
  }
}

resource "aws_cognito_user_pool_client" "this" {
  name         = "${var.name_prefix}-web"
  user_pool_id = aws_cognito_user_pool.this.id

  # Public SPA client: no client secret.
  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  supported_identity_providers = ["COGNITO"]

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]

  # Extra callback/logout URLs (e.g. the deployed CloudFront SPA) are merged
  # with the localhost defaults so both local dev and the hosted demo work.
  callback_urls = distinct(concat(var.callback_urls, var.extra_callback_urls))
  logout_urls   = distinct(concat(var.logout_urls, var.extra_logout_urls))

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  prevent_user_existence_errors = "ENABLED"
}

# Hosted-UI domain on the free *.auth.<region>.amazoncognito.com namespace, so
# the browser login/PKCE flow works without a custom domain. The prefix must be
# globally unique across all AWS accounts.
resource "aws_cognito_user_pool_domain" "this" {
  count        = var.hosted_ui_domain_prefix == "" ? 0 : 1
  domain       = var.hosted_ui_domain_prefix
  user_pool_id = aws_cognito_user_pool.this.id
}
