# Storage module (skeleton).
#
# Responsibility: private S3 buckets for uploaded PDFs and generated artifacts
# (public access blocked, versioning/encryption), plus the CloudFront/S3
# hosting for the frontend. Uploads/downloads use short-lived presigned URLs.
#
# Resources are added in the upload and frontend-hosting task groups.
