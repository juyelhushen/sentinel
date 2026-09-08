from pathlib import Path

import pytest

from sentinel.bootstrap.application import create_sentinel_application
from sentinel.domain.models.incident import Incident
from sentinel.llm.base import LLMProvider
from sentinel.llm.models import LLMRequest, LLMResponse


class FakeLLMProvider(LLMProvider):
    """Fake LLM provider for application integration tests."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content="""
            {
                "summary": "Search for token validation.",
                "steps": [
                    {
                        "step_number": 1,
                        "action": "search_code",
                        "description": "Find token validation code.",
                        "arguments": {
                            "query": "validate_token"
                        }
                    }
                ]
            }
            """,
            model="fake-model",
        )

    async def health_check(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_sentinel_application_runs_end_to_end(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "service.py"

    source_file.write_text(
        "def validate_token():\n"
        "    return True\n",
        encoding="utf-8",
    )

    application = create_sentinel_application(
        llm_provider=FakeLLMProvider(),
        repository_root=tmp_path,
    )

    incident = Incident(
        title="Token validation issue",
        description="Token validation may be failing.",
        repository="example-repository",
    )

    result = await application.ainvoke(
        {
            "incident": incident,
            "plan": None,
            "investigation": None,
            "error": None,
        }
    )

    assert result["error"] is None
    assert result["investigation"] is not None
    assert len(result["investigation"].step_results) == 1
    assert result["investigation"].step_results[0].success is True