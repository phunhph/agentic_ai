"""LangGraph connector scaffold.

This module provides a small wrapper around LangGraph usage patterns.
If `langgraph` package is not installed, the module exposes stubs with
instructions on how to install and configure it.
"""
import os
import logging

try:
    import langgraph
    HAS_LANGGRAPH = True
except Exception:
    HAS_LANGGRAPH = False

logger = logging.getLogger(__name__)


class LangGraphClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('LANGGRAPH_API_KEY')
        if not HAS_LANGGRAPH:
            logger.warning('langgraph package not installed. LangGraphClient will operate in stub mode.')

    def build_and_run(self, graph_spec: dict):
        """Build and run a LangGraph graph from a high-level spec.

        This is a scaffold: users should replace with concrete LangGraph graph
        construction logic according to their LangGraph version.
        """
        if not HAS_LANGGRAPH:
            logger.info('Stub: would run LangGraph with spec: %s', graph_spec)
            return {"status": "stub", "spec": graph_spec}

        # Example (pseudo-code) for real LangGraph usage
        try:
            # The real API will differ; this is a placeholder
            graph = langgraph.Graph.from_spec(graph_spec)
            result = graph.run(api_key=self.api_key)
            return result
        except Exception as e:
            logger.exception('LangGraph run failed: %s', e)
            return {"status": "error", "error": str(e)}


def build_extraction_spec(text: str, fields: list = None) -> dict:
    """Return a simple LangGraph-style spec for extracting structured fields.

    The spec format is intentionally generic — replace with the concrete
    spec your LangGraph version expects.
    """
    fields = fields or ["name", "budget", "status", "bant_need", "mixs"]
    return {
        "type": "extraction",
        "input": text,
        "fields": fields,
        "instructions": "Extract the requested fields and return a JSON object mapping field->value. Use codes for choices when possible."
    }
