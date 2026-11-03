from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode

PLACEHOLDERS = {"", "replace-me"}


class Settings(BaseSettings):
    database_url: str = "postgresql://kb:replace-me@localhost:5432/kb"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
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
    livekit_token_ttl_seconds: int = Field(default=900, gt=0)
    internal_api_token: str = ""
    # Load the embedding models when the API starts. Tests turn it off.
    warm_models: bool = True
    auth_jwks_url: str = "http://localhost:3000/api/auth/jwks"
    auth_issuer: str = "http://localhost:3000"
    session_rate_limit: int = Field(default=10, gt=0)
    linear_client_id: str = ""
    linear_client_secret: str = ""
    linear_redirect_uri: str = "http://localhost:3000/api/integrations/linear/callback"
    # 32 random bytes in base64. It encrypts stored tokens and signs OAuth state.
    linear_token_key: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @property
    def async_database_url(self) -> str:
        scheme, _, rest = self.database_url.partition("://")
        if scheme in ("postgres", "postgresql"):
            return f"postgresql+asyncpg://{rest}"
        return self.database_url


@lru_cache
def load_settings() -> Settings:
    return Settings()
