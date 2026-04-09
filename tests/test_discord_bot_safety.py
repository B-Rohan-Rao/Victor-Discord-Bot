import uuid
from typing import Any, cast

import pytest

from src.discord_bot import SingleInstanceLock, bot, safe_defer_interaction


class _DummyResponse:
    def __init__(self, error: Exception | None = None):
        self.error = error

    async def defer(self, thinking: bool = True):
        if self.error is not None:
            raise self.error
        return None


class _DummyInteraction:
    def __init__(self, error: Exception | None = None):
        self.response = _DummyResponse(error=error)


class _AlreadyAcknowledgedError(Exception):
    code = 40060


@pytest.mark.asyncio
async def test_safe_defer_interaction_returns_false_for_acknowledged_error():
    interaction = _DummyInteraction(error=_AlreadyAcknowledgedError("already acknowledged"))
    ok = await safe_defer_interaction(cast(Any, interaction))
    assert ok is False


@pytest.mark.asyncio
async def test_safe_defer_interaction_raises_other_errors():
    interaction = _DummyInteraction(error=RuntimeError("boom"))
    with pytest.raises(RuntimeError, match="boom"):
        await safe_defer_interaction(cast(Any, interaction))


@pytest.mark.asyncio
async def test_safe_defer_interaction_success():
    interaction = _DummyInteraction()
    ok = await safe_defer_interaction(cast(Any, interaction))
    assert ok is True


def test_single_instance_lock_blocks_second_acquire():
    lock_name = f"autonomous-research-agent-test-{uuid.uuid4().hex}.lock"
    lock_a = SingleInstanceLock(name=lock_name)
    lock_b = SingleInstanceLock(name=lock_name)

    assert lock_a.acquire() is True
    try:
        assert lock_b.acquire() is False
    finally:
        lock_a.release()

    assert lock_b.acquire() is True
    lock_b.release()


def test_command_registry_has_only_health_name():
    names = [cmd.name for cmd in bot.tree.get_commands()]
    assert "health" in names
    assert "heath" not in names
