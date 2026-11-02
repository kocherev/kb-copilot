import asyncio

from alembic import context
from kb_api.db import Base
from kb_api.settings import load_settings
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine


def include_object(
    obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    """Compare only the API's tables. Better Auth and ingest own the others."""
    if type_ == "table":
        return name in Base.metadata.tables
    table = getattr(obj, "table", None)
    return table is None or table.name in Base.metadata.tables


def run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def main() -> None:
    engine = create_async_engine(load_settings().async_database_url)
    async with engine.connect() as connection:
        await connection.run_sync(run)
    await engine.dispose()


asyncio.run(main())
