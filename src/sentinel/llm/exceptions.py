class LLMError(Exception):
    """Base exception for LLM errors"""


class LLMConnectionError(LLMError):
    """Raised when the LLM provider cannot be reached."""


class LLMTimeoutError(LLMError):
    """Raised when an LLM request times out."""


class LLMResponseError(LLMError):
    """Raised when an LLM returns an invalid response."""
