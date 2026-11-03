"""The API's two knowledge routes, answered in this process from a kb_rag index.

For selfcheck and tests. The worker never imports this module.
"""

import json
from dataclasses import asdict

import httpx
from kb_rag import RetrievalSettings, search, supported_ids
from qdrant_client import AsyncQdrantClient


def local_api(
    client: AsyncQdrantClient, settings: RetrievalSettings
) -> httpx.MockTransport:
    async def answer(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path == "/internal/search":
            found = await search(
                client,
                body["product_id"],
                body["query"],
                limit=body["limit"],
                settings=settings,
            )
            return httpx.Response(200, json=asdict(found))
        ids = await supported_ids(
            client,
            body["product_id"],
            body["answer"],
            body["passage_ids"],
            settings=settings,
        )
        return httpx.Response(200, json={"passage_ids": ids})

    return httpx.MockTransport(answer)
