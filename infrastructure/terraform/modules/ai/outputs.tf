output "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID (KNOWLEDGE_BASE_ID for the agents)."
  value       = awscc_bedrock_knowledge_base.graphrag.knowledge_base_id
}

output "knowledge_base_data_source_id" {
  description = "KB S3 data source ID (KNOWLEDGE_BASE_DATA_SOURCE_ID)."
  value       = awscc_bedrock_data_source.chunks.data_source_id
}

output "kb_chunk_bucket_name" {
  description = "Prepared-chunk bucket name (KB_CHUNK_BUCKET_NAME)."
  value       = aws_s3_bucket.kb_chunks.id
}

output "graphrag_graph_arn" {
  description = "Neptune Analytics graph ARN."
  value       = aws_neptunegraph_graph.graphrag.arn
}
