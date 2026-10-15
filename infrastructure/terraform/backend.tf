# Remote state backend for the main stack.
#
# The bucket/table come from the bootstrap config (see bootstrap/). Backend
# blocks can't use variables, so the concrete values are supplied at init time
# via -backend-config, which also lets the same config target dev or prod state.
#
#   terraform init ^
#     -backend-config="bucket=book-companion-dev-tfstate" ^
#     -backend-config="key=dev/terraform.tfstate" ^
#     -backend-config="region=eu-central-1"
#
# State locking uses native S3 locking (use_lockfile=true), which writes a
# <key>.tflock object next to the state. DynamoDB-based locking is deprecated
# per the HashiCorp S3 backend docs, so no lock table is needed.
#
# To keep using local state (e.g. before bootstrapping), comment out the
# `backend "s3"` block below and run `terraform init` normally.

terraform {
  backend "s3" {
    encrypt      = true
    use_lockfile = true
    # bucket, key, region supplied via -backend-config at init.
  }
}
