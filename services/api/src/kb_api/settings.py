import os

from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str
    qdrant_url: str
    data_root: str
    cors_origins: list[str]


def _csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql://kb:replace-me@localhost:5432/kb",
        ),
        qdrant_url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
        data_root=os.environ.get("KB_DATA_ROOT", "."),
        cors_origins=_csv(
            os.environ.get(
                "CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000",
            )
        ),
    )
