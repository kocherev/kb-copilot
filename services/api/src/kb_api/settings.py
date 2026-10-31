import os

from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str
    qdrant_url: str


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql://kb:replace-me@localhost:5432/kb",
        ),
        qdrant_url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
    )
