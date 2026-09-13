"""Local authentication smoke test."""

import getpass

from app.government.api_client import (
    SafeHireAPIClient,
    SafeHireAPIError,
)


def main() -> None:
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")

    client = SafeHireAPIClient()

    try:
        login_result = client.login(
            username=username,
            password=password,
        )

        profile = client.get_current_user()

    except SafeHireAPIError as error:
        print(
            "Authentication failed: {}".format(
                error.message
            )
        )
        return

    print("Login successful.")
    print(
        "Username: {}".format(
            login_result.get("username")
        )
    )
    print(
        "Role: {}".format(
            login_result.get("role")
        )
    )
    print(
        "Profile display name: {}".format(
            profile.get("display_name")
        )
    )


if __name__ == "__main__":
    main()