"""Adaptive-reading LangGraph graph.

Pipeline (design.md):

    load_content → budget → rank → select → generate(model) → validate → refs

Only the ``generate`` node calls the model (via the text-generation tool);
every other node is a deterministic algorithm. Tool ports are injected so the
graph is testable with fakes.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.adaptive_reading import nodes
from src.agents.adaptive_reading.state import ReadingState
from src.agents.shared.ports import BookContentPort, TextGenerationPort


def build_reading_graph(
    content: BookContentPort, generator: TextGenerationPort
) -> CompiledStateGraph:
    """Compile the adaptive-reading graph with the given tool ports."""

    def load_node(state: ReadingState) -> ReadingState:
        chunks = content.get_chunks(
            user_id=state["user_id"],
            book_id=state["book_id"],
            chapter_id=state.get("chapter_id"),
        )
        return {"chunks": chunks}

    def budget_node(state: ReadingState) -> ReadingState:
        return {"budget_words": nodes.word_budget(state["duration_minutes"])}

    def select_node(state: ReadingState) -> ReadingState:
        ranked = nodes.rank_sections(state["chunks"], focus=state["focus"])
        selected = nodes.select_to_budget(
            ranked, budget_words=state["budget_words"]
        )
        return {"selected": selected}

    def generate_node(state: ReadingState) -> ReadingState:
        prompt = nodes.build_prompt(
            state["selected"],
            mode=state["mode"],
            focus=state["focus"],
            budget_words=state["budget_words"],
        )
        raw = generator.generate(prompt=prompt, max_words=state["budget_words"])
        content = nodes.validate_output(raw, budget_words=state["budget_words"])
        return {
            "prompt": prompt,
            "content": content,
            "source_refs": nodes.dedupe_source_refs(state["selected"]),
        }

    graph = StateGraph(ReadingState)
    graph.add_node("load", load_node)
    graph.add_node("budget", budget_node)
    graph.add_node("select", select_node)
    graph.add_node("generate", generate_node)

    graph.add_edge(START, "load")
    graph.add_edge("load", "budget")
    graph.add_edge("budget", "select")
    graph.add_edge("select", "generate")
    graph.add_edge("generate", END)

    return graph.compile()
