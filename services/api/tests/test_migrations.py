from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

API_TABLES = {
    "products",
    "api_keys",
    "audit_log",
    "live_sessions",
    "rate_limit_hits",
    "ingest_jobs",
    "documents",
    "linear_connections",
    "linear_state_uses",
    "escalations",
}
ALEMBIC = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def tables(engine: Engine) -> set[str]:
    with engine.connect() as connection:
        return set(inspect(connection).get_table_names())


def test_migrations_create_and_drop_the_api_tables(sync_engine: Engine) -> None:
    assert API_TABLES <= tables(sync_engine)

    command.downgrade(ALEMBIC, "base")

    assert not API_TABLES & tables(sync_engine)


def test_upgrade_keeps_a_products_table_from_before_migrations(
    sync_engine: Engine,
) -> None:
    command.downgrade(ALEMBIC, "base")
    with sync_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE products (id TEXT PRIMARY KEY, name TEXT NOT NULL,"
                " description TEXT NOT NULL, tone TEXT NOT NULL,"
                " refusal_rules TEXT NOT NULL)"
            )
        )
        connection.execute(
            text("INSERT INTO products VALUES ('old-1', 'Old', 'd', 't', 'r')")
        )

    try:
        command.upgrade(ALEMBIC, "head")
        with sync_engine.connect() as connection:
            legacy = connection.execute(
                text("SELECT id, name FROM products_legacy")
            ).all()
            columns = {
                column["name"] for column in inspect(connection).get_columns("products")
            }
    finally:
        with sync_engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS products_legacy"))
    assert [tuple(row) for row in legacy] == [("old-1", "Old")]
    assert "org_id" in columns


def test_models_match_the_migrations_and_ignore_other_tables(
    sync_engine: Engine,
) -> None:
    # A stand-in for a Better Auth table, unless the database has it.
    created = {"member"} - tables(sync_engine)
    with sync_engine.begin() as connection:
        for table in created:
            connection.execute(text(f"CREATE TABLE {table} (id TEXT PRIMARY KEY)"))
    try:
        command.check(ALEMBIC)
    finally:
        with sync_engine.begin() as connection:
            for table in created:
                connection.execute(text(f"DROP TABLE {table}"))


def test_upgrade_keeps_ingest_jobs_from_before_migrations(sync_engine: Engine) -> None:
    command.downgrade(ALEMBIC, "base")
    with sync_engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE ingest_jobs (id TEXT PRIMARY KEY, product_id TEXT)")
        )
        connection.execute(text("INSERT INTO ingest_jobs VALUES ('job-1', 'old-1')"))

    try:
        command.upgrade(ALEMBIC, "head")
        with sync_engine.connect() as connection:
            legacy = connection.execute(
                text("SELECT id, product_id FROM ingest_jobs_legacy")
            ).all()
            columns = {
                column["name"]
                for column in inspect(connection).get_columns("ingest_jobs")
            }
    finally:
        with sync_engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS ingest_jobs_legacy"))
    assert [tuple(row) for row in legacy] == [("job-1", "old-1")]
    assert {"status", "chunk_count", "error"} <= columns
