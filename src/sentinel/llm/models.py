from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class LLMMessage:
    """A message to send to LLM."""

    role: str
    content: str


@dataclass(frozen=True)
class LLMRequest:
    """A request to send to LLM provider."""

    messages: tuple[LLMMessage, ...]
    temperature: float = 0.0
    max_token: int | None = None
    request_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class LLMResponse:
    """Response returned from LLM provider."""

    content: str
    model: str
    request_id: UUID = field(default_factory=uuid4)
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None
