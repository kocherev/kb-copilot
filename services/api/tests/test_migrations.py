from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

API_TABLES = {"products", "api_keys", "audit_log", "live_sessions", "rate_limit_hits"}
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def tables(engine: Engine) -> set[str]:
    with engine.connect() as connection:
        return set(inspect(connection).get_table_names())


def test_migrations_create_and_drop_the_api_tables(sync_engine: Engine) -> None:
    assert API_TABLES <= tables(sync_engine)

    command.downgrade(Config(str(ALEMBIC_INI)), "base")

    assert not API_TABLES & tables(sync_engine)
