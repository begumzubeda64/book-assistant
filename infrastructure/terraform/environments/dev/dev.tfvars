environment = "dev"
aws_region  = "eu-central-1"
project     = "book-companion"

# GraphRAG graph-construction model: Claude Sonnet 4 via the EU cross-Region
# inference profile (bare foundation-model ARNs are not invokable in eu-central-1).
graph_construction_model_arn = "arn:aws:bedrock:eu-central-1:169424236454:inference-profile/eu.anthropic.claude-sonnet-4-20250514-v1:0"
