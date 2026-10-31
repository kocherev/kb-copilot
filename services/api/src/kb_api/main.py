from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from kb_api.ingest import router
from kb_api.settings import Settings, load_settings

app = FastAPI(title="kb-copilot")
app.include_router(router)


class Health(BaseModel):
    status: Literal["ok"]


@app.get("/health")
def health() -> Health:
    return Health(status="ok")


def current_settings() -> Settings:
    return load_settings()
