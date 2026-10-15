environment = "dev"
aws_region  = "eu-central-1"
project     = "book-companion"

# GraphRAG graph-construction model: Claude Haiku 4.5 via the EU cross-Region
# inference profile. GraphRAG chunk entity extraction only accepts Claude
# Haiku-family models (Sonnet is rejected with "Invalid graph bedrock foundation
# model provided"); Haiku 4.5 is the model AWS uses in its official GraphRAG
# example. Bare foundation-model ARNs are not invokable in eu-central-1, so this
# is the EU inference-profile ARN.
graph_construction_model_arn = "arn:aws:bedrock:eu-central-1:169424236454:inference-profile/eu.anthropic.claude-haiku-4-5-20251001-v1:0"
