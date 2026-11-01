import os

from pydantic import BaseModel


class Settings(BaseModel):
    database_url: str
    qdrant_url: str
    qdrant_api_key: str
    data_root: str
    cors_origins: list[str]
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str


def _csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql://kb:replace-me@localhost:5432/kb",
        ),
        qdrant_url=os.environ.get("QDRANT_URL", "http://localhost:6333"),
        qdrant_api_key=os.environ.get("QDRANT_API_KEY", ""),
        data_root=os.environ.get("KB_DATA_ROOT", "."),
        cors_origins=_csv(
            os.environ.get(
                "CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000",
            )
        ),
        livekit_url=os.environ.get("LIVEKIT_URL", ""),
        livekit_api_key=os.environ.get("LIVEKIT_API_KEY", ""),
        livekit_api_secret=os.environ.get("LIVEKIT_API_SECRET", ""),
    )
