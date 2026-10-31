from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from kb_api.ingest import router
from kb_api.products import router as products_router
from kb_api.sessions import router as sessions_router
from kb_api.settings import Settings, load_settings

app = FastAPI(title="kb-copilot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=load_settings().cors_origins,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["content-type"],
)
app.include_router(router)
app.include_router(products_router)
app.include_router(sessions_router)


class Health(BaseModel):
    status: Literal["ok"]


@app.get("/health")
def health() -> Health:
    return Health(status="ok")


def current_settings() -> Settings:
    return load_settings()
