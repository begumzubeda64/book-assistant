# ECR module (skeleton).
#
# Responsibility: ECR repositories for every deployable image, with image
# scanning on push and a lifecycle policy to expire untagged images:
#   - api                 (FastAPI service)
#   - mcp                 (MCP tool server)
#   - agent-ingestion     (ingestion agent)
#   - agent-adaptive      (adaptive-reading agent)
#   - agent-discussion    (discussion agent)
#
# The three agent repos are separate because the agents are isolated images
# (see decisions.md).
#
# Resources are added in the infrastructure task group.
