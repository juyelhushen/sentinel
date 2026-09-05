from dataclasses import dataclass

from sentinel.llm.models import LLMMessage


@dataclass(frozen=True)
class Prompt:
    """Represents a structured prompt."""

    system: str
    user: str

    def to_message(self) -> tuple[LLMMessage, ...]:
        """Converts the prompt to a LLM message."""

        return (
            LLMMessage(
                role="system",
                content=self.system,
            ),
            LLMMessage(
                role="user",
                content=self.user,
            ),
        )
