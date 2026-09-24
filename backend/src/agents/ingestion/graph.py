"""Ingestion LangGraph graph.

Wires the deterministic nodes into a linear graph:

    fetch_pdf -> extract_text -> chunk -> ingest

The graph body is pure processing; job-status transitions (PROCESSING ->
COMPLETED/FAILED) are handled by the agent entrypoint around the graph so the
graph stays testable in isolation. Building the graph takes the tool ports so
tests can inject fakes.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.ingestion import nodes
from src.agents.ingestion.state import IngestionState
from src.agents.shared.ports import ContentStorePort, KnowledgeBasePort


def build_ingestion_graph(
    content: ContentStorePort, kb: KnowledgeBasePort
) -> CompiledStateGraph:
    """Compile the ingestion graph with the given tool ports."""

    def fetch_node(state: IngestionState) -> IngestionState:
        pdf = nodes.fetch_pdf(content, state["user_id"], state["object_key"])
        return {"pdf_bytes": pdf}

    def extract_node(state: IngestionState) -> IngestionState:
        return {"pages": nodes.extract_pages(state["pdf_bytes"])}

    def chunk_node(state: IngestionState) -> IngestionState:
        return {"chunks": nodes.chunk_pages(state["book_id"], state["pages"])}

    def ingest_node(state: IngestionState) -> IngestionState:
        ref = nodes.ingest_chunks(
            kb,
            user_id=state["user_id"],
            book_id=state["book_id"],
            chunks=state["chunks"],
        )
        return {"ingestion_ref": ref}

    graph = StateGraph(IngestionState)
    graph.add_node("fetch", fetch_node)
    graph.add_node("extract", extract_node)
    graph.add_node("chunk", chunk_node)
    graph.add_node("ingest", ingest_node)

    graph.add_edge(START, "fetch")
    graph.add_edge("fetch", "extract")
    graph.add_edge("extract", "chunk")
    graph.add_edge("chunk", "ingest")
    graph.add_edge("ingest", END)

    return graph.compile()
