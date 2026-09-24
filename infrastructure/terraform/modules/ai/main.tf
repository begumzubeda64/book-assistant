# AI module (skeleton).
#
# Responsibility:
#   - Bedrock Knowledge Base + Neptune Analytics for GraphRAG.
#   - THREE Amazon Bedrock AgentCore Runtimes, one per isolated agent
#     (ingestion, adaptive-reading, discussion), each referencing its own agent
#     container image, execution role, and endpoint (see decisions.md).
#   - The MCP tool server's runtime wiring (its ECS service or AgentCore host)
#     and its least-privilege role.
# All in eu-central-1.
#
# Each tier gets its own least-privilege IAM role (see security.md).
#
# Resources are added in the ingestion/GraphRAG and agent task groups.
