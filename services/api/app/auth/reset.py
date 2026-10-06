"""Local-only administrator reset: python -m app.auth.reset USERNAME."""
import argparse
import getpass
import sys

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.service import AuthError, reset_password
from app.infrastructure.database import get_engine


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset an account password and revoke all sessions.")
    parser.add_argument("username")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error("Interactive terminal required; passwords cannot be passed as arguments or piped.")
    password = getpass.getpass("New password (6–20 characters): ")
    if password != getpass.getpass("Confirm password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 1
    try:
        with Session(get_engine()) as db:
            reset_password(db, args.username, password)
    except (AuthError, SQLAlchemyError):
        print("Reset failed. Check account, password length and database availability.", file=sys.stderr)
        return 1
    print("Password reset. All sessions revoked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
