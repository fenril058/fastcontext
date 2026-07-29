import os

import pytest


def _endpoint_configured() -> bool:
    """Mirror the FC_*/legacy env resolution used by agent_factory."""
    base_url = os.getenv("FC_BASE_URL") or os.getenv("BASE_URL")
    model = os.getenv("FC_MODEL") or os.getenv("MODEL")
    return bool(base_url and model)


requires_llm = pytest.mark.skipif(
    not _endpoint_configured(),
    reason="needs a live OpenAI-compatible endpoint (set FC_BASE_URL and FC_MODEL)",
)
