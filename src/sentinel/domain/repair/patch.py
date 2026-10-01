from abc import ABC, abstractmethod


class PatchApplicationError(ValueError):
    """Raised when a patch cannot be safely applied."""


class PatchApplier(ABC):
    """Applies a patch to text."""

    @abstractmethod
    def apply(self, original: str, patch: str) -> str:
        raise NotImplementedError