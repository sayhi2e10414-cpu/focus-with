from __future__ import annotations

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


settings.data_dir.mkdir(parents=True, exist_ok=True)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def _migrate_interventions(bind: Engine) -> None:
    """Generalize the v0.5 interventions table without losing existing data."""
    inspector = inspect(bind)
    if "interventions" not in inspector.get_table_names():
        return
    columns = {column["name"]: column for column in inspector.get_columns("interventions")}
    already_current = (
        "source_type" in columns
        and "source_event_id" in columns
        and columns["phone_open_event_id"].get("nullable", False)
    )
    if already_current:
        return

    legacy_table = "interventions_before_camera_events"
    if legacy_table in inspector.get_table_names():
        raise RuntimeError(
            f"Cannot migrate interventions while the recovery table {legacy_table!r} exists"
        )
    legacy_indexes = inspector.get_indexes("interventions")
    with bind.begin() as connection:
        connection.exec_driver_sql(f'ALTER TABLE "interventions" RENAME TO "{legacy_table}"')

        # SQLite keeps explicit index names after a table rename. Remove those
        # names so SQLAlchemy can create the replacement table and its indexes.
        for index in legacy_indexes:
            name = index.get("name")
            if name and not name.startswith("sqlite_autoindex"):
                quoted = connection.dialect.identifier_preparer.quote(name)
                connection.exec_driver_sql(f"DROP INDEX IF EXISTS {quoted}")

        from . import models

        models.Intervention.__table__.create(connection)
        source_type = "source_type" if "source_type" in columns else "'phone_app'"
        source_event_id = (
            "source_event_id"
            if "source_event_id" in columns
            else "CASE WHEN phone_open_event_id IS NOT NULL "
                 "THEN 'phone_app:' || phone_open_event_id ELSE NULL END"
        )
        connection.exec_driver_sql(
            f"""
            INSERT INTO interventions (
                id, session_id, task_id, phone_open_event_id, source_type, source_event_id,
                app_name, opened_at, closed_at, duration_seconds, strike_number, status,
                message, punishment, sent_at, resolved_at, created_at
            )
            SELECT
                id, session_id, task_id, phone_open_event_id, {source_type}, {source_event_id},
                app_name, opened_at, closed_at, duration_seconds, strike_number, status,
                message, punishment, sent_at, resolved_at, created_at
            FROM "{legacy_table}"
            """
        )
        connection.exec_driver_sql(f'DROP TABLE "{legacy_table}"')


def initialize_database(bind: Engine = engine) -> None:
    # Populate Base.metadata even when this function is called directly by the
    # installer before any route or service modules have been imported.
    from . import models as _models  # noqa: F401

    _migrate_interventions(bind)
    Base.metadata.create_all(bind)
    seed_session = sessionmaker(bind=bind, expire_on_commit=False)()
    try:
        from .services.rewards import ensure_reward_defaults

        ensure_reward_defaults(seed_session)
        seed_session.commit()
    except Exception:
        seed_session.rollback()
        raise
    finally:
        seed_session.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
