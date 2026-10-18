import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Job:
    name: str
    # Returns how many tickets it changed, for the log.
    run: Callable[[], Awaitable[int]]


class Lease(Protocol):
    # False when another worker holds it, or the lease store can't be reached.
    async def acquire(self) -> bool: ...

    async def release(self) -> None: ...


# Runs every job once per interval. Any number of worker processes can run side by side for
# availability; the lease lets only one of them do a pass at a time, so they don't all load
# the same tickets and trip each other's optimistic locks.
class Worker:
    def __init__(self, jobs: Sequence[Job], lease: Lease, *, every: timedelta) -> None:
        self._jobs = jobs
        self._lease = lease
        self._every = every

    async def run_until(self, stop: asyncio.Event) -> None:
        logger.info("worker started; a pass every %s", self._every)
        while not stop.is_set():
            await self.run_once()
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self._every.total_seconds())
        logger.info("worker stopped")

    async def run_once(self) -> None:
        if not await self._lease.acquire():
            logger.debug("another worker holds the lease; skipping this pass")
            return
        try:
            for job in self._jobs:
                await self._run(job)
        finally:
            await self._lease.release()

    @staticmethod
    async def _run(job: Job) -> None:
        try:
            changed = await job.run()
        except Exception:
            # One failing job must not starve the others or kill the process; the traceback
            # goes to the log and the job gets another chance on the next pass.
            logger.exception("job %s failed", job.name)
            return
        if changed:
            logger.info("job %s: %d ticket(s) changed", job.name, changed)
