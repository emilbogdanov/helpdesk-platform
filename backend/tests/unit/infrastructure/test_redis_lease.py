import logging
from datetime import timedelta
from typing import TYPE_CHECKING, cast

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from helpdesk.infrastructure.redis_lease import RedisLease

if TYPE_CHECKING:
    from redis.asyncio import Redis


class DropsBeforeRelease:
    """Redis answering the acquire, then going away before the pass ends."""

    def lock(self, *_: object, **__: object) -> "DropsBeforeRelease":
        return self

    async def acquire(self) -> bool:
        return True

    async def release(self) -> None:
        raise RedisConnectionError("Connection reset by peer")


async def test_losing_redis_mid_pass_only_warns(caplog: pytest.LogCaptureFixture) -> None:
    # Release runs in the worker's finally block; raising there would end the process.
    lease = RedisLease(cast("Redis", DropsBeforeRelease()), "lease", ttl=timedelta(seconds=30))
    assert await lease.acquire()

    with caplog.at_level(logging.WARNING, logger="helpdesk.infrastructure.redis_lease"):
        await lease.release()

    assert caplog.messages == ["can't reach Redis to release the worker lease; it will expire"]
