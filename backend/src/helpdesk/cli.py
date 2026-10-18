import argparse
import asyncio
import getpass
import os
import signal
import sys
from collections.abc import Sequence
from contextlib import suppress

from helpdesk.application.errors import EmailTakenError
from helpdesk.application.users.admin_bootstrap import register_admin
from helpdesk.config import Settings
from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.users.user import User
from helpdesk.domain.users.values import DisplayName, EmailAddress, Password
from helpdesk.main import build_container, build_worker, configure_logging

# Read from the environment when set, so scripts and containers can run the command
# without a terminal to type into.
PASSWORD_VARIABLE = "HELPDESK_ADMIN_PASSWORD"  # noqa: S105 - a variable name, not a secret


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="helpdesk")
    commands = parser.add_subparsers(dest="command", required=True)
    create_admin = commands.add_parser(
        "create-admin",
        help="create an admin account, e.g. the first one on a fresh install",
        description=f"The password is read from {PASSWORD_VARIABLE} or prompted for.",
    )
    create_admin.add_argument("--email", required=True)
    create_admin.add_argument("--name", required=True, help="display name")
    commands.add_parser(
        "worker", help="run the background jobs: overdue first responses and auto-close"
    )
    args = parser.parse_args(argv)

    if args.command == "worker":
        return _worker()
    return _create_admin(email=args.email, name=args.name)


def _create_admin(*, email: str, name: str) -> int:
    password = os.environ.get(PASSWORD_VARIABLE) or getpass.getpass("Password: ")
    try:
        admin = asyncio.run(
            _register_admin(
                email=EmailAddress(email),
                display_name=DisplayName(name),
                password=Password(password),
            )
        )
    except (InvalidValueError, EmailTakenError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    sys.stdout.write(f"created admin {admin.email} ({admin.id})\n")
    return 0


async def _register_admin(
    *, email: EmailAddress, display_name: DisplayName, password: Password
) -> User:
    container = build_container(Settings())
    try:
        return await register_admin(
            container.uow_factory(),
            container.hasher,
            container.clock,
            email=email,
            display_name=display_name,
            password=password,
        )
    finally:
        await container.close()


def _worker() -> int:
    # Ctrl+C on Windows, where asyncio can't install signal handlers, arrives as this.
    with suppress(KeyboardInterrupt):
        asyncio.run(run_worker(Settings()))
    return 0


async def run_worker(settings: Settings, stop: asyncio.Event | None = None) -> None:
    configure_logging(settings)
    process = build_worker(settings)
    stop = stop or _stop_on_signals()
    try:
        await process.worker.run_until(stop)
    finally:
        await process.close()


def _stop_on_signals() -> asyncio.Event:
    # SIGTERM is how Docker asks a container to stop; finishing the current pass first
    # means no ticket is left half-processed.
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_number in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signal_number, stop.set)
    return stop
