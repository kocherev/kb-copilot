from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from kb_api.api_keys import router as api_keys_router
from kb_api.auth import AUTH_ERRORS, UserPrincipal, jwks_client, require_user
from kb_api.ingest import router
from kb_api.products import router as products_router
from kb_api.sessions import router as sessions_router
from kb_api.settings import load_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    app.state.sessions = async_sessionmaker(engine, expire_on_commit=False)
    app.state.jwks = jwks_client(settings.auth_jwks_url)
    yield
    await engine.dispose()


app = FastAPI(title="kb-copilot", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=load_settings().cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["authorization", "content-type"],
)
app.include_router(router)
app.include_router(products_router)
app.include_router(sessions_router)
app.include_router(api_keys_router)


class Health(BaseModel):
    status: Literal["ok"]


class Me(BaseModel):
    user_id: str
    org_id: str


@app.get("/health")
def health() -> Health:
    return Health(status="ok")


@app.get("/me", tags=["me"], responses=AUTH_ERRORS)
async def me(principal: Annotated[UserPrincipal, Depends(require_user)]) -> Me:
    return Me(user_id=principal.user_id, org_id=principal.org_id)
