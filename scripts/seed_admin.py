"""Create the initial SafeHire administrator account."""

import argparse
import getpass
import os
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.core.security import hash_password
from src.db.models import SessionLocal, User, init_db


MINIMUM_PASSWORD_LENGTH = 12


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Create the initial SafeHire administrator."
        )
    )

    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help=(
            "Read administrator details from environment "
            "variables instead of interactive prompts."
        ),
    )

    return parser.parse_args()


def require_value(
    value: str | None,
    environment_name: str,
) -> str:
    """Require a non-empty environment value."""

    cleaned_value = (value or "").strip()

    if not cleaned_value:
        raise ValueError(
            "{} is required.".format(
                environment_name
            )
        )

    return cleaned_value


def validate_password(password: str) -> str:
    """Validate the administrator password."""

    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise ValueError(
            "The administrator password must contain "
            "at least {} characters.".format(
                MINIMUM_PASSWORD_LENGTH
            )
        )

    return password


def prompt_non_empty(label: str) -> str:
    """Prompt until a non-empty value is entered."""

    while True:
        value = input(label).strip()

        if value:
            return value

        print("This value is required.")


def prompt_password() -> str:
    """Prompt for and confirm a password."""

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


def get_interactive_credentials() -> tuple[str, str, str]:
    """Collect administrator details interactively."""

    username = prompt_non_empty(
        "Administrator username: "
    ).lower()

    display_name = prompt_non_empty(
        "Administrator display name: "
    )

    password = prompt_password()

    return username, display_name, password


def get_environment_credentials() -> tuple[str, str, str]:
    """Read administrator details from environment variables."""

    username = require_value(
        os.getenv("ADMIN_USERNAME"),
        "ADMIN_USERNAME",
    ).lower()

    display_name = require_value(
        os.getenv("ADMIN_DISPLAY_NAME"),
        "ADMIN_DISPLAY_NAME",
    )

    password = validate_password(
        require_value(
            os.getenv("ADMIN_PASSWORD"),
            "ADMIN_PASSWORD",
        )
    )

    return username, display_name, password


def create_administrator(
    username: str,
    display_name: str,
    password: str,
) -> bool:
    """Create an administrator when the username is available."""

    init_db()

    with SessionLocal() as session:
        existing_user = session.scalar(
            select(User).where(
                User.username == username
            )
        )

        if existing_user is not None:
            print(
                "A user with that username already exists."
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
                "The administrator account could not be "
                "created because of a database error."
            )
            raise

        print(
            "Administrator account created successfully."
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

        return True


def main() -> None:
    """Run the administrator seeding workflow."""

    arguments = parse_arguments()

    try:
        if arguments.non_interactive:
            credentials = get_environment_credentials()
        else:
            credentials = get_interactive_credentials()

        create_administrator(
            username=credentials[0],
            display_name=credentials[1],
            password=credentials[2],
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