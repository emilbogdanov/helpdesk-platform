import argparse
import asyncio
import getpass
import os
import sys
from collections.abc import Sequence

from helpdesk.application.errors import EmailTakenError
from helpdesk.application.users.admin_bootstrap import register_admin
from helpdesk.config import Settings
from helpdesk.domain.errors import InvalidValueError
from helpdesk.domain.users.user import User
from helpdesk.domain.users.values import DisplayName, EmailAddress, Password
from helpdesk.main import build_container

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
    args = parser.parse_args(argv)

    password = os.environ.get(PASSWORD_VARIABLE) or getpass.getpass("Password: ")
    try:
        admin = asyncio.run(
            _create_admin(
                email=EmailAddress(args.email),
                display_name=DisplayName(args.name),
                password=Password(password),
            )
        )
    except (InvalidValueError, EmailTakenError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    sys.stdout.write(f"created admin {admin.email} ({admin.id})\n")
    return 0


async def _create_admin(
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
