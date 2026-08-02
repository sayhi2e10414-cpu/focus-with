from __future__ import annotations

from sqlalchemy import create_engine, inspect

from app.database import initialize_database


def test_v051_interventions_are_migrated_without_data_loss(tmp_path):
    database_path = tmp_path / "focus.db"
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE interventions (
                id INTEGER PRIMARY KEY,
                session_id INTEGER NOT NULL,
                task_id INTEGER,
                phone_open_event_id INTEGER NOT NULL,
                app_name VARCHAR(120) NOT NULL,
                opened_at DATETIME NOT NULL,
                closed_at DATETIME,
                duration_seconds INTEGER NOT NULL,
                strike_number INTEGER NOT NULL,
                status VARCHAR(32) NOT NULL,
                message TEXT,
                punishment TEXT,
                sent_at DATETIME,
                resolved_at DATETIME,
                created_at DATETIME NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX ix_interventions_phone_open_event_id "
            "ON interventions (phone_open_event_id)"
        )
        connection.exec_driver_sql(
            """
            INSERT INTO interventions (
                id, session_id, task_id, phone_open_event_id, app_name, opened_at,
                duration_seconds, strike_number, status, created_at
            ) VALUES (
                7, 3, 2, 11, 'Xiaohongshu', '2026-08-02 10:00:00',
                20, 1, 'sent', '2026-08-02 10:00:00'
            )
            """
        )

    initialize_database(engine)
    columns = {column["name"]: column for column in inspect(engine).get_columns("interventions")}
    assert columns["phone_open_event_id"]["nullable"] is True
    assert "source_type" in columns
    assert "source_event_id" in columns
    with engine.connect() as connection:
        row = connection.exec_driver_sql(
            "SELECT id, phone_open_event_id, source_type, source_event_id "
            "FROM interventions"
        ).one()
    assert tuple(row) == (7, 11, "phone_app", "phone_app:11")
    assert {
        "reward_definitions",
        "reward_settings",
        "reward_progress",
        "reward_grants",
    }.issubset(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM reward_definitions"
        ).scalar_one() == 1
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM reward_settings"
        ).scalar_one() == 1

    # Startup is intentionally repeatable.
    initialize_database(engine)
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM reward_definitions"
        ).scalar_one() == 1
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM reward_settings"
        ).scalar_one() == 1
