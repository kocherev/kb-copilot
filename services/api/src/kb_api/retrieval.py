"""Search and citation checks for the agent. The API holds the only embedding models."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from kb_rag import search, supported_ids
from pydantic import BaseModel, Field, StringConstraints

from kb_api.auth import AUTH_ERRORS, InternalCaller, require_internal

# Not in the OpenAPI schema: the browser client never calls these.
router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    responses=AUTH_ERRORS,
    include_in_schema=False,
)

ProductId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[^\s/]+$")
]


class SearchRequest(BaseModel):
    product_id: ProductId
    query: Annotated[str, StringConstraints(max_length=2000)]
    limit: int = Field(default=5, ge=1, le=20)


class FoundPassage(BaseModel):
    id: str
    title: str
    source: str
    anchor: str
    text: str
    score: float


class SearchResponse(BaseModel):
    passages: list[FoundPassage]
    abstained: bool
    timings_ms: dict[str, float]


class CitationsRequest(BaseModel):
    product_id: ProductId
    answer: Annotated[str, StringConstraints(max_length=20000)]
    passage_ids: Annotated[list[UUID], Field(max_length=20)]


class CitationsResponse(BaseModel):
    passage_ids: list[str]


@router.post("/search")
async def search_passages(
    body: SearchRequest,
    request: Request,
    _: Annotated[InternalCaller, Depends(require_internal)],
) -> SearchResponse:
    found = await search(
        request.app.state.qdrant,
        body.product_id,
        body.query,
        limit=body.limit,
        settings=request.app.state.retrieval,
    )
    return SearchResponse(
        passages=[
            FoundPassage.model_validate(passage, from_attributes=True)
            for passage in found.passages
        ],
        abstained=found.abstained,
        timings_ms=found.timings_ms,
    )


@router.post("/citations")
async def check_citations(
    body: CitationsRequest,
    request: Request,
    _: Annotated[InternalCaller, Depends(require_internal)],
) -> CitationsResponse:
    ids = await supported_ids(
        request.app.state.qdrant,
        body.product_id,
        body.answer,
        [str(passage_id) for passage_id in body.passage_ids],
        settings=request.app.state.retrieval,
    )
    return CitationsResponse(passage_ids=ids)
