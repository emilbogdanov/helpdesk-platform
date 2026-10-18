import logging
from datetime import timedelta

from redis.asyncio import Redis
from redis.exceptions import LockError, RedisError

logger = logging.getLogger(__name__)


# A Redis lock held for one worker pass. The TTL is a safety net for a worker that dies
# mid-pass: the lease frees itself instead of blocking every other worker forever.
class RedisLease:
    def __init__(self, client: Redis, name: str, *, ttl: timedelta) -> None:
        self._lock = client.lock(name, timeout=ttl.total_seconds(), blocking=False)

    async def acquire(self) -> bool:
        try:
            acquired: bool = await self._lock.acquire()
        except RedisError:
            # No Redis means no pass rather than a crash: the worker keeps retrying each
            # interval and picks up where it left off once Redis is back.
            logger.warning("can't reach Redis for the worker lease; skipping this pass")
            return False
        return acquired

    async def release(self) -> None:
        try:
            await self._lock.release()
        except LockError:
            # The pass outlived the TTL, so another worker may have started one. Harmless,
            # since every change is re-checked and version-guarded, but worth knowing about.
            logger.warning("worker lease expired before the pass finished; raise its TTL")
        except RedisError:
            logger.warning("can't reach Redis to release the worker lease; it will expire")
