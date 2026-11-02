from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    database_url: str = "postgresql://kb:replace-me@localhost:5432/kb"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    data_root: str = Field(default=".", validation_alias="KB_DATA_ROOT")
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    livekit_url: str = ""
    # Server-side LiveKit API calls. In Compose the browser URL is not reachable
    # from the API container, so this can point at the internal host instead.
    livekit_api_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


@lru_cache
def load_settings() -> Settings:
    return Settings()
