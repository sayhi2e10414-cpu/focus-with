from __future__ import annotations

import argparse

from . import models
from .database import Base, SessionLocal, engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Administer FocusWith OAuth connections")
    parser.add_argument("command", choices=["status", "revoke-all"])
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        counts = {
            "clients": db.query(models.OAuthClient).count(),
            "tokens": db.query(models.OAuthTokenRecord).count(),
        }
        if args.command == "status":
            print(f"Registered OAuth clients: {counts['clients']}")
            print(f"Stored token records: {counts['tokens']}")
            return

        for model in (
            models.OAuthTokenRecord,
            models.OAuthAuthorizationCodeRecord,
            models.OAuthLoginFailure,
            models.OAuthLoginRequest,
            models.OAuthClient,
        ):
            db.query(model).delete(synchronize_session=False)
        db.commit()
        print("All Remote MCP clients, grants, and tokens were revoked.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
