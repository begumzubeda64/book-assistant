"""Discussion LangGraph graph.

    retrieve (GraphRAG) → generate (model) → citations

GraphRAG retrieval and generation go through the MCP tools (injected as ports);
citations are derived deterministically from what was retrieved. The graph is
invoked directly for short interactive turns (design.md), not via SQS.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.discussion import nodes
from src.agents.discussion.state import DiscussionState
from src.agents.shared.ports import GraphRAGRetrievalPort, TextGenerationPort

# A grounded answer should be concise; cap the generation word budget.
ANSWER_WORD_BUDGET = 400


def build_discussion_graph(
    retriever: GraphRAGRetrievalPort, generator: TextGenerationPort
) -> CompiledStateGraph:
    """Compile the discussion graph with the given tool ports."""

    def retrieve_node(state: DiscussionState) -> DiscussionState:
        passages = retriever.retrieve(
            user_id=state["user_id"],
            book_id=state["book_id"],
            query=state["question"],
        )
        return {"passages": passages}

    def generate_node(state: DiscussionState) -> DiscussionState:
        prompt = nodes.build_grounded_prompt(
            state["question"],
            state["passages"],
            state.get("history", []),
            state.get("summary"),
            state.get("persona_voice"),
        )
        answer = generator.generate(prompt=prompt, max_words=ANSWER_WORD_BUDGET)
        return {
            "prompt": prompt,
            "answer": answer.strip(),
            "citations": nodes.passages_to_citations(state["passages"]),
        }

    graph = StateGraph(DiscussionState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()
