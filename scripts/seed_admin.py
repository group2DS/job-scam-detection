"""Create the initial Hakiki Hire administrator account."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.core.security import hash_password
from src.db.models import SessionLocal, User, init_db


MINIMUM_PASSWORD_LENGTH = 12


def parse_arguments() -> argparse.Namespace:
    """Parse command-line options for local or deployment seeding."""

    parser = argparse.ArgumentParser(
        description=(
            "Create the initial Hakiki Hire administrator account."
        )
    )

    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help=(
            "Read administrator details from environment variables "
            "instead of interactive prompts."
        ),
    )

    return parser.parse_args()


def prompt_non_empty(label: str) -> str:
    """Prompt until a non-empty value is entered."""

    while True:
        value = input(label).strip()

        if value:
            return value

        print("This value is required.")


def require_environment_value(
    variable_name: str,
) -> str:
    """Return a required non-empty environment-variable value."""

    value = os.getenv(variable_name, "").strip()

    if not value:
        raise ValueError(
            "{} is required in non-interactive mode.".format(
                variable_name
            )
        )

    return value


def validate_password(password: str) -> str:
    """Validate the administrator password without displaying it."""

    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise ValueError(
            "The administrator password must contain at least "
            "{} characters.".format(MINIMUM_PASSWORD_LENGTH)
        )

    return password


def prompt_password() -> str:
    """Prompt for a password and matching confirmation."""

    while True:
        password = getpass.getpass(
            "Administrator password: "
        )

        confirmation = getpass.getpass(
            "Confirm administrator password: "
        )

        if password != confirmation:
            print("The passwords do not match.")
            continue

        try:
            return validate_password(password)
        except ValueError as error:
            print(str(error))


def get_interactive_credentials() -> Tuple[str, str, str]:
    """Collect administrator credentials using terminal prompts."""

    username = prompt_non_empty(
        "Administrator username: "
    ).lower()

    display_name = prompt_non_empty(
        "Administrator display name: "
    )

    password = prompt_password()

    return username, display_name, password


def get_environment_credentials() -> Tuple[str, str, str]:
    """Read administrator credentials from deployment variables."""

    username = require_environment_value(
        "ADMIN_USERNAME"
    ).lower()

    display_name = require_environment_value(
        "ADMIN_DISPLAY_NAME"
    )

    password = validate_password(
        require_environment_value(
            "ADMIN_PASSWORD"
        )
    )

    return username, display_name, password


def create_administrator(
    username: str,
    display_name: str,
    password: str,
) -> bool:
    """Create an administrator unless the username already exists."""

    init_db()

    with SessionLocal() as session:
        existing_user = session.scalar(
            select(User).where(
                User.username == username
            )
        )

        if existing_user is not None:
            print(
                "A user with username '{}' already exists.".format(
                    username
                )
            )
            return False

        administrator = User(
            username=username,
            display_name=display_name,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
        )

        try:
            session.add(administrator)
            session.commit()
            session.refresh(administrator)

        except SQLAlchemyError:
            session.rollback()
            print(
                "The Hakiki Hire administrator account could not "
                "be created because of a database error."
            )
            raise

        print(
            "Hakiki Hire administrator account created successfully."
        )
        print(
            "Username: {}".format(
                administrator.username
            )
        )
        print(
            "Display name: {}".format(
                administrator.display_name
            )
        )
        print(
            "Role: {}".format(
                administrator.role
            )
        )
        print(
            "Active: {}".format(
                administrator.is_active
            )
        )

        return True


def main() -> None:
    """Run the interactive or deployment-safe seeding workflow."""

    arguments = parse_arguments()

    try:
        if arguments.non_interactive:
            username, display_name, password = (
                get_environment_credentials()
            )
        else:
            username, display_name, password = (
                get_interactive_credentials()
            )

        create_administrator(
            username=username,
            display_name=display_name,
            password=password,
        )

    except ValueError as error:
        print(
            "Configuration error: {}".format(
                error
            )
        )
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
