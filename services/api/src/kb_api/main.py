import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Annotated, Literal

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kb_rag import DEFAULT_SETTINGS, RetrievalSettings
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from kb_api.api_keys import router as api_keys_router
from kb_api.auth import AUTH_ERRORS, UserPrincipal, jwks_client, require_user
from kb_api.escalations import router as escalations_router
from kb_api.ingest import router as ingest_router
from kb_api.integrations import router as integrations_router
from kb_api.jobs import index_forever, requeue_interrupted
from kb_api.products import router as products_router
from kb_api.retrieval import router as retrieval_router
from kb_api.sessions import router as sessions_router
from kb_api.settings import load_settings


def load_models(settings: RetrievalSettings) -> None:
    settings.dense.query("warm")
    settings.sparse.query("warm")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
    app.state.sessions = async_sessionmaker(engine, expire_on_commit=False)
    app.state.jwks = jwks_client(settings.auth_jwks_url)
    # A large file goes up as one big upsert, so the default 5 s is too short.
    qdrant = AsyncQdrantClient(
        url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=120
    )
    app.state.qdrant = qdrant
    app.state.retrieval = DEFAULT_SETTINGS
    app.state.wake = asyncio.Event()
    await requeue_interrupted(app.state.sessions)
    worker = asyncio.create_task(index_forever(app))
    # The first search of a live session should not wait for the models to load.
    warm = (
        asyncio.create_task(asyncio.to_thread(load_models, DEFAULT_SETTINGS))
        if settings.warm_models
        else None
    )
    yield
    worker.cancel()
    if warm:
        warm.cancel()
    with suppress(asyncio.CancelledError):
        await worker
    await qdrant.close()
    await engine.dispose()


app = FastAPI(title="kb-copilot", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=load_settings().cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["authorization", "content-type"],
)
app.include_router(ingest_router)
app.include_router(products_router)
app.include_router(sessions_router)
app.include_router(api_keys_router)
app.include_router(integrations_router)
app.include_router(escalations_router)
app.include_router(retrieval_router)


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
