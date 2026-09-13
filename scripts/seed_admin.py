"""Create the initial SafeHire administrator account."""

import getpass
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


def prompt_non_empty(label: str) -> str:
    """Prompt repeatedly until the user enters a non-empty value."""

    while True:
        value = input(label).strip()

        if value:
            return value

        print("This value is required.")


def prompt_password() -> str:
    """Prompt for a password and require matching confirmation."""

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

        if len(password) < MINIMUM_PASSWORD_LENGTH:
            print(
                "Use a password containing at least "
                "{} characters.".format(
                    MINIMUM_PASSWORD_LENGTH
                )
            )
            continue

        return password


def main() -> None:
    """Create the initial administrator if the username is available."""

    init_db()

    username = prompt_non_empty(
        "Administrator username: "
    ).lower()

    display_name = prompt_non_empty(
        "Administrator display name: "
    )

    password = prompt_password()

    with SessionLocal() as session:
        statement = select(User).where(
            User.username == username
        )

        existing_user = session.scalar(statement)

        if existing_user is not None:
            print(
                "A user with that username already exists."
            )
            return

        administrator = User(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            role="admin",
            is_active=True,
        )

        try:
            session.add(administrator)
            session.commit()
            session.refresh(administrator)

        except SQLAlchemyError as error:
            session.rollback()

            print(
                "The administrator account could not be created."
            )
            print(
                "Database error: {}".format(
                    error.__class__.__name__
                )
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

        print(
            "Active: {}".format(
                administrator.is_active
            )
        )


if __name__ == "__main__":
    main()