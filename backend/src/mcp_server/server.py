"""MCP tool server.

Exposes a small, explicitly allowlisted set of tools to the agents over the
Model Context Protocol. This is the isolated tool tier: agents call these tools
instead of touching AWS directly, and a misbehaving tool is contained here
(decisions.md, security.md).

Security model:
- IAM/SigV4 only: the server runs as an AgentCore runtime; the only callers are
  the agent execution roles granted bedrock-agentcore:InvokeAgentRuntime on this
  runtime's ARN. There is no public endpoint.
- Per-job user scoping: tools NEVER trust a caller-supplied user_id. Each tool
  derives the trusted user_id from a signed scope token (minted by the
  dispatcher, verified here), passed in the MCP request `_meta.scope_token`. A
  compromised agent therefore cannot act as another user.
- Allowlist: only the tools below are registered; nothing else is reachable.

Allowlisted tools:
- get_authorized_content   : fetch an authorized user's uploaded PDF bytes
- ingest_to_knowledge_base : ingest prepared chunks into the KB (GraphRAG)
- get_book_content         : read prepared chunks for an authorized book
- generate_text            : foundation-model text generation
- store_reading_result     : persist an adaptive-reading result
- graphrag_retrieve        : user-scoped GraphRAG retrieval
"""

import base64
from typing import Any

from src.agents.shared.ports import (
    BookContentPort,
    GraphRAGRetrievalPort,
    ReadingStorePort,
    TextGenerationPort,
)
from src.agents.shared.types import PreparedChunk
from src.core.config import Settings
from src.mcp_server.scope import JobScope, verify_scope_token
from src.mcp_server.tools.book_content import BookContentTool, ReadingStoreTool
from src.mcp_server.tools.content import ContentTool
from src.mcp_server.tools.generation import TextGenerationTool
from src.mcp_server.tools.graphrag import GraphRAGRetrievalTool
from src.mcp_server.tools.knowledge_base import KnowledgeBaseTool

# The single source of truth for what the agents are permitted to invoke.
TOOL_ALLOWLIST = frozenset(
    {
        "get_authorized_content",
        "ingest_to_knowledge_base",
        "get_book_content",
        "generate_text",
        "store_reading_result",
        "graphrag_retrieve",
    }
)


class ToolBundle:
    """All real tool adapters the MCP server exposes."""

    def __init__(
        self,
        *,
        content: ContentTool,
        knowledge_base: KnowledgeBaseTool,
        book_content: BookContentTool,
        generation: TextGenerationTool,
        reading_store: ReadingStoreTool,
        graphrag: GraphRAGRetrievalTool,
    ) -> None:
        self.content = content
        self.knowledge_base = knowledge_base
        self.book_content = book_content
        self.generation = generation
        self.reading_store = reading_store
        self.graphrag = graphrag


def build_tools_from_settings(settings: Settings) -> ToolBundle:
    """Construct the real tool adapters from configuration (boto3-backed)."""
    import boto3

    s3 = boto3.client(
        "s3", region_name=settings.aws_region, endpoint_url=settings.aws_endpoint_url
    )
    bedrock_agent = boto3.client("bedrock-agent", region_name=settings.aws_region)
    bedrock_agent_runtime = boto3.client(
        "bedrock-agent-runtime", region_name=settings.aws_region
    )
    bedrock_runtime = boto3.client("bedrock-runtime", region_name=settings.aws_region)

    if not settings.uploads_bucket_name:
        raise RuntimeError("uploads_bucket_name is required for the MCP server")
    if not (
        settings.kb_chunk_bucket_name
        and settings.knowledge_base_id
        and settings.knowledge_base_data_source_id
    ):
        raise RuntimeError("Knowledge Base configuration is incomplete")
    if not settings.reading_results_bucket_name:
        raise RuntimeError("reading_results_bucket_name is required for the MCP server")

    return ToolBundle(
        content=ContentTool(s3, settings.uploads_bucket_name),
        knowledge_base=KnowledgeBaseTool(
            s3_client=s3,
            bedrock_agent_client=bedrock_agent,
            chunk_bucket=settings.kb_chunk_bucket_name,
            knowledge_base_id=settings.knowledge_base_id,
            data_source_id=settings.knowledge_base_data_source_id,
        ),
        book_content=BookContentTool(s3, settings.kb_chunk_bucket_name),
        generation=TextGenerationTool(bedrock_runtime, settings.generation_model_id),
        reading_store=ReadingStoreTool(s3, settings.reading_results_bucket_name),
        graphrag=GraphRAGRetrievalTool(
            bedrock_agent_runtime, settings.knowledge_base_id
        ),
    )


def _scope_from_context(ctx: Any, secret: str) -> JobScope:
    """Extract and verify the signed scope token from the MCP request _meta.

    Fails closed: any missing/forged/expired token raises, so a tool cannot run
    without a verified, trusted user_id.
    """
    meta = getattr(getattr(ctx, "request_context", None), "meta", None)
    extra = getattr(meta, "model_extra", None) or {}
    token = extra.get("scope_token") if isinstance(extra, dict) else None
    return verify_scope_token(token or "", secret=secret)


def create_mcp_server(tools: ToolBundle, *, scope_secret: str) -> Any:
    """Create the FastMCP server with the allowlisted, scope-enforced tools.

    Every tool derives the trusted user_id from the verified scope token in the
    request _meta and ignores any user_id in the call arguments.
    """
    from mcp.server.fastmcp import Context, FastMCP

    server = FastMCP("book-companion-tools", host="0.0.0.0", stateless_http=True)

    @server.tool(name="get_authorized_content")
    def get_authorized_content(object_key: str, ctx: Context) -> str:
        """Return base64-encoded PDF bytes for an authorized object."""
        scope = _scope_from_context(ctx, scope_secret)
        raw = tools.content.fetch_pdf_bytes(scope.user_id, object_key)
        return base64.b64encode(raw).decode("ascii")

    @server.tool(name="ingest_to_knowledge_base")
    def ingest_to_knowledge_base(
        book_id: str, chunks: list[dict[str, Any]], ctx: Context
    ) -> str:
        """Ingest prepared chunks into the Knowledge Base; returns a ref."""
        scope = _scope_from_context(ctx, scope_secret)
        prepared = [PreparedChunk.model_validate(c) for c in chunks]
        return tools.knowledge_base.ingest_chunks(
            user_id=scope.user_id, book_id=book_id, chunks=prepared
        )

    @server.tool(name="get_book_content")
    def get_book_content(
        book_id: str, ctx: Context, chapter_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Return prepared chunks for an authorized book/chapter."""
        scope = _scope_from_context(ctx, scope_secret)
        chunks = tools.book_content.get_chunks(
            user_id=scope.user_id, book_id=book_id, chapter_id=chapter_id
        )
        return [c.model_dump() for c in chunks]

    @server.tool(name="generate_text")
    def generate_text(prompt: str, max_words: int, ctx: Context) -> str:
        """Generate text for the prompt (foundation model)."""
        # Generation has no user data surface, but still require a valid scope
        # so an unauthenticated caller cannot burn model spend.
        _scope_from_context(ctx, scope_secret)
        return tools.generation.generate(prompt=prompt, max_words=max_words)

    @server.tool(name="store_reading_result")
    def store_reading_result(reading_id: str, payload: str, ctx: Context) -> str:
        """Store a generated adaptive-reading result; returns its location."""
        scope = _scope_from_context(ctx, scope_secret)
        return tools.reading_store.store_reading(
            user_id=scope.user_id, reading_id=reading_id, payload=payload
        )

    @server.tool(name="graphrag_retrieve")
    def graphrag_retrieve(
        book_id: str, query: str, ctx: Context, top_k: int = 8
    ) -> list[dict[str, Any]]:
        """Retrieve passages relevant to the query (user-scoped)."""
        scope = _scope_from_context(ctx, scope_secret)
        passages = tools.graphrag.retrieve(
            user_id=scope.user_id, book_id=book_id, query=query, top_k=top_k
        )
        return [p.model_dump() for p in passages]

    return server


# Backwards-compatible registration helpers kept for targeted tests.
def register_reading_tools(
    server: Any,
    *,
    book_content: BookContentPort,
    generator: TextGenerationPort,
    reading_store: ReadingStorePort,
) -> None:  # pragma: no cover - superseded by create_mcp_server
    raise NotImplementedError(
        "Tools are registered with scope enforcement in create_mcp_server"
    )


def register_discussion_tools(
    server: Any, *, retriever: GraphRAGRetrievalPort
) -> None:  # pragma: no cover - superseded by create_mcp_server
    raise NotImplementedError(
        "Tools are registered with scope enforcement in create_mcp_server"
    )
