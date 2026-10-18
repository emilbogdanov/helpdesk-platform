import asyncio
import logging
from datetime import timedelta

import pytest
from redis.asyncio import Redis

from helpdesk.infrastructure.redis_lease import RedisLease

pytestmark = pytest.mark.integration

NAME = "helpdesk:worker:lease"


async def test_only_one_worker_holds_the_lease_at_a_time(redis: Redis) -> None:
    first = RedisLease(redis, NAME, ttl=timedelta(seconds=30))
    second = RedisLease(redis, NAME, ttl=timedelta(seconds=30))

    assert await first.acquire()
    assert not await second.acquire()

    await first.release()
    assert await second.acquire()


async def test_a_lease_left_by_a_dead_worker_expires(redis: Redis) -> None:
    crashed = RedisLease(redis, NAME, ttl=timedelta(milliseconds=200))
    survivor = RedisLease(redis, NAME, ttl=timedelta(seconds=30))
    assert await crashed.acquire()

    await asyncio.sleep(0.3)

    assert await survivor.acquire()


async def test_releasing_an_expired_lease_only_warns(
    redis: Redis, caplog: pytest.LogCaptureFixture
) -> None:
    slow = RedisLease(redis, NAME, ttl=timedelta(milliseconds=100))
    assert await slow.acquire()
    await asyncio.sleep(0.2)

    with caplog.at_level(logging.WARNING, logger="helpdesk.infrastructure.redis_lease"):
        await slow.release()

    assert "worker lease expired before the pass finished; raise its TTL" in caplog.messages


async def test_unreachable_redis_skips_the_pass_instead_of_crashing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Port 1 is never a Redis server; the connection is refused straight away.
    nowhere = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=1)
    lease = RedisLease(nowhere, NAME, ttl=timedelta(seconds=30))

    with caplog.at_level(logging.WARNING, logger="helpdesk.infrastructure.redis_lease"):
        assert not await lease.acquire()

    assert caplog.messages == ["can't reach Redis for the worker lease; skipping this pass"]
    await nowhere.aclose()
