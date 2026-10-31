"""Mint a participant token and dispatch the support agent."""

import json
from typing import Protocol
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from livekit import api
from pydantic import BaseModel

from kb_api.products import ProductStore, get_product_store
from kb_api.settings import Settings, load_settings

router = APIRouter()

AGENT_NAME = "kb-support"


class SessionCreate(BaseModel):
    product_id: UUID


class SessionGrant(BaseModel):
    url: str
    token: str
    room: str


class AgentDispatch(BaseModel):
    agent_name: str
    room: str
    metadata: str


class Dispatcher(Protocol):
    async def create_dispatch(self, request: AgentDispatch) -> None: ...


class LiveKitDispatcher:
    def __init__(self, url: str, api_key: str, api_secret: str) -> None:
        self._url = url
        self._api_key = api_key
        self._api_secret = api_secret

    async def create_dispatch(self, request: AgentDispatch) -> None:
        async with api.LiveKitAPI(self._url, self._api_key, self._api_secret) as client:
            await client.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    agent_name=request.agent_name,
                    room=request.room,
                    metadata=request.metadata,
                )
            )


def livekit_ready(settings: Settings) -> bool:
    url = settings.livekit_url
    key = settings.livekit_api_key
    secret = settings.livekit_api_secret
    return bool(url and key and secret)


def participant_token(settings: Settings, room: str, identity: str) -> str:
    return (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .to_jwt()
    )


def get_dispatcher() -> Dispatcher:
    settings = load_settings()
    return LiveKitDispatcher(
        settings.livekit_url,
        settings.livekit_api_key,
        settings.livekit_api_secret,
    )


@router.post("/sessions", status_code=201)
async def create_session(
    body: SessionCreate,
    store: ProductStore = Depends(get_product_store),
    dispatcher: Dispatcher = Depends(get_dispatcher),
) -> SessionGrant:
    product_id = str(body.product_id)
    if store.get(product_id) is None:
        raise HTTPException(status_code=404, detail="product not found")
    settings = load_settings()
    if not livekit_ready(settings):
        raise HTTPException(status_code=503, detail="LiveKit is not configured")
    room = f"kb-{uuid4()}"
    identity = "user"
    grant = SessionGrant(
        url=settings.livekit_url,
        token=participant_token(settings, room, identity),
        room=room,
    )
    try:
        await dispatcher.create_dispatch(
            AgentDispatch(
                agent_name=AGENT_NAME,
                room=room,
                metadata=json.dumps({"product_id": product_id}),
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not dispatch the agent",
        ) from exc
    return grant
