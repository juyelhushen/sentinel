from typing import Protocol


class RateLimitStore(Protocol):
    async def check_and_record(
        self,
        api_key: str,
        endpoint: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> int | None: ...
