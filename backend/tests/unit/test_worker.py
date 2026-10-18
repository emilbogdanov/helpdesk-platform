import asyncio
import logging
from datetime import timedelta

import pytest

from helpdesk.worker import Job, Worker


class FakeLease:
    def __init__(self, *, held_elsewhere: bool = False) -> None:
        self.held_elsewhere = held_elsewhere
        self.released = 0

    async def acquire(self) -> bool:
        return not self.held_elsewhere

    async def release(self) -> None:
        self.released += 1


def recording(name: str, log: list[str], *, changed: int = 0) -> Job:
    async def run() -> int:
        log.append(name)
        return changed

    return Job(name, run)


def failing(name: str) -> Job:
    async def run() -> int:
        raise RuntimeError("database went away")

    return Job(name, run)


async def test_a_pass_runs_every_job_in_order_and_releases_the_lease() -> None:
    ran: list[str] = []
    lease = FakeLease()

    await Worker(
        [recording("first", ran), recording("second", ran)], lease, every=timedelta(0)
    ).run_once()

    assert ran == ["first", "second"]
    assert lease.released == 1


async def test_no_pass_while_another_worker_holds_the_lease() -> None:
    ran: list[str] = []
    lease = FakeLease(held_elsewhere=True)

    await Worker([recording("first", ran)], lease, every=timedelta(0)).run_once()

    assert ran == []
    assert lease.released == 0


async def test_a_failing_job_is_logged_and_the_rest_still_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ran: list[str] = []
    lease = FakeLease()

    with caplog.at_level(logging.ERROR, logger="helpdesk.worker"):
        await Worker(
            [failing("flaky"), recording("next", ran)], lease, every=timedelta(0)
        ).run_once()

    assert ran == ["next"]
    assert lease.released == 1
    assert caplog.records[0].message == "job flaky failed"
    assert caplog.records[0].exc_info is not None


async def test_changes_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="helpdesk.worker"):
        await Worker(
            [recording("close-resolved-tickets", [], changed=3)], FakeLease(), every=timedelta(0)
        ).run_once()

    assert "job close-resolved-tickets: 3 ticket(s) changed" in caplog.messages


async def test_runs_a_pass_per_interval_until_stopped() -> None:
    stop = asyncio.Event()
    passes = 0

    async def count_and_stop_after_three() -> int:
        nonlocal passes
        passes += 1
        if passes == 3:
            stop.set()
        return 0

    await Worker(
        [Job("count", count_and_stop_after_three)], FakeLease(), every=timedelta(0)
    ).run_until(stop)

    assert passes == 3


async def test_does_nothing_if_stopped_before_starting() -> None:
    ran: list[str] = []
    stop = asyncio.Event()
    stop.set()

    await Worker([recording("first", ran)], FakeLease(), every=timedelta(seconds=60)).run_until(
        stop
    )

    assert ran == []
