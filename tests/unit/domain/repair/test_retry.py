import pytest

from sentinel.domain.repair.retry import RepairRetryPolicy


def test_allows_retry_before_max_attempts() -> None:
    policy = RepairRetryPolicy(max_attempts=3)

    assert policy.can_retry(1)
    assert policy.can_retry(2)
    
def test_does_not_allow_retry_at_max_attempts() -> None:
    policy = RepairRetryPolicy(max_attempts=3)

    assert not policy.can_retry(3)
    
def test_rejects_invalid_max_attempts() -> None:
    with pytest.raises(
        ValueError,
        match="at least 1",
    ):
        RepairRetryPolicy(max_attempts=0)