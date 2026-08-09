import pytest

from sentinel.domain.enums.task_status import TaskStatus
from sentinel.domain.models.task import Task


def test_task_starts_as_pending() -> None:
    task = Task(
        title="Inspect authentication",
        description="Find authentication implementation",
    )

    assert task.status == TaskStatus.PENDING


def test_task_can_start_and_complete() -> None:
    task = Task(
        title="Inspect authentication",
        description="Find authentication implementation",
    )

    task.start()
    task.complete()

    assert task.status == TaskStatus.COMPLETED


def test_task_cannot_complete_before_starting() -> None:
    task = Task(
        title="Inspect authentication",
        description="Find authentication implementation",
    )

    with pytest.raises(ValueError):
        task.complete()
