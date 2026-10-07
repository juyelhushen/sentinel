from dataclasses import dataclass


@dataclass(frozen=True)
class RepairRetryPolicy:
    
    max_attempts:int = 3

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")

    def can_retry(self, current_attempt: int) -> bool:
        return current_attempt < self.max_attempts

    