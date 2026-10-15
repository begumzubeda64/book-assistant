# Remote state backend for the main stack.
#
# The bucket/table come from the bootstrap config (see bootstrap/). Backend
# blocks can't use variables, so the concrete values are supplied at init time
# via -backend-config, which also lets the same config target dev or prod state.
#
#   terraform init \
#     -backend-config="bucket=book-companion-dev-tfstate" \
#     -backend-config="dynamodb_table=book-companion-dev-tflock" \
#     -backend-config="key=dev/terraform.tfstate" \
#     -backend-config="region=eu-central-1"
#
# To keep using local state (e.g. before bootstrapping), comment out the
# `backend "s3"` block below and run `terraform init` normally.

terraform {
  backend "s3" {
    encrypt = true
    # bucket, dynamodb_table, key, region supplied via -backend-config at init.
  }
}
