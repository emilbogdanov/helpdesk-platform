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
from helpdesk.application.users.password_reset import reset_password
from helpdesk.config import Settings
from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.users.user import User
from helpdesk.domain.users.values import DisplayName, EmailAddress, Password
from helpdesk.main import build_container, build_worker, configure_logging

# Read from the environment when set, so scripts and containers can run the commands
# without a terminal to type into.
PASSWORD_VARIABLE = "HELPDESK_PASSWORD"  # noqa: S105 - a variable name, not a secret


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
    reset_password_command = commands.add_parser(
        "reset-password",
        help="set a new password for an account, e.g. after it was forgotten",
        description=f"The new password is read from {PASSWORD_VARIABLE} or prompted for.",
    )
    reset_password_command.add_argument("--email", required=True)
    commands.add_parser(
        "worker", help="run the background jobs: overdue first responses and auto-close"
    )
    args = parser.parse_args(argv)

    match args.command:
        case "create-admin":
            return _create_admin(email=args.email, name=args.name)
        case "reset-password":
            return _reset_password(email=args.email)
        case _:
            return _worker()


def _create_admin(*, email: str, name: str) -> int:
    try:
        admin = asyncio.run(
            _register_admin(
                email=EmailAddress(email),
                display_name=DisplayName(name),
                password=Password(_read_password()),
            )
        )
    except (InvalidValueError, EmailTakenError) as error:
        return _fail(error)
    sys.stdout.write(f"created admin {admin.email} ({admin.id})\n")
    return 0


def _reset_password(*, email: str) -> int:
    try:
        address = EmailAddress(email)
        user = asyncio.run(_set_password(email=address, password=Password(_read_password())))
    except InvalidValueError as error:
        return _fail(error)
    if user is None:
        return _fail(f"no account uses {address}")
    sys.stdout.write(f"new password set for {user.email}\n")
    return 0


def _read_password() -> str:
    if from_environment := os.environ.get(PASSWORD_VARIABLE):
        return from_environment
    # Typed blind, so a typo would otherwise lock the account out on the spot.
    password = getpass.getpass("Password: ")
    if getpass.getpass("Repeat it: ") != password:
        raise InvalidValueError("the two passwords don't match")
    return password


def _fail(error: Exception | str) -> int:
    sys.stderr.write(f"error: {error}\n")
    return 1


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


async def _set_password(*, email: EmailAddress, password: Password) -> User | None:
    container = build_container(Settings())
    try:
        return await reset_password(
            container.uow_factory(), container.hasher, email=email, password=password
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
