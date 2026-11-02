"""Org-scoped product configuration."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from kb_rag import RetrievalSettings
from pydantic import BaseModel, ConfigDict, StringConstraints
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kb_api.audit import audit
from kb_api.auth import (
    AUTH_ERRORS,
    ErrorBody,
    InternalCaller,
    Principal,
    get_principal,
    get_reader,
)
from kb_api.db import DocumentRow, ProductRow, get_db
from kb_api.jobs import get_qdrant, get_retrieval_settings, remove_chunks

NOT_FOUND: dict[int | str, dict[str, object]] = {
    404: {"model": ErrorBody, "description": "No such product in this org"}
}

router = APIRouter(tags=["products"], responses=AUTH_ERRORS)

OneLine = r"^[^\r\n]*$"
Name = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=120, pattern=OneLine
    ),
]
# One paragraph: the web form joins lines before it sends the description.
Description = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=2000, pattern=OneLine
    ),
]
Tone = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=200, pattern=OneLine
    ),
]
RefusalRules = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]


class ProductWrite(BaseModel):
    name: Name
    description: Description
    tone: Tone
    refusal_rules: RefusalRules


class Product(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    tone: str
    refusal_rules: str


async def load_owned_product(
    db: AsyncSession, org_id: str, product_id: UUID
) -> ProductRow:
    """Return the product if this org owns it. Another org's product is a 404."""
    found = await db.scalar(
        select(ProductRow).where(
            ProductRow.id == product_id, ProductRow.org_id == org_id
        )
    )
    if found is None:
        raise HTTPException(status_code=404, detail="product not found")
    return found


async def owned_product(
    product_id: UUID,
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductRow:
    return await load_owned_product(db, principal.org_id, product_id)


@router.get("/products")
async def list_products(
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Product]:
    rows = await db.scalars(
        select(ProductRow)
        .where(ProductRow.org_id == principal.org_id)
        .order_by(ProductRow.created_at.desc())
    )
    return [Product.model_validate(row) for row in rows]


@router.post("/products", status_code=201)
async def create_product(
    body: ProductWrite,
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Product:
    row = ProductRow(org_id=principal.org_id, **body.model_dump())
    db.add(row)
    await db.flush()
    audit(db, principal, "product.create", f"product:{row.id}", {"name": row.name})
    await db.commit()
    return Product.model_validate(row)


@router.get("/products/{product_id}", responses=NOT_FOUND)
async def read_product(
    product_id: UUID,
    reader: Annotated[Principal | InternalCaller, Depends(get_reader)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Product:
    if isinstance(reader, Principal):
        return Product.model_validate(
            await load_owned_product(db, reader.org_id, product_id)
        )
    found = await db.get(ProductRow, product_id)
    if found is None:
        raise HTTPException(status_code=404, detail="product not found")
    return Product.model_validate(found)


@router.put("/products/{product_id}", responses=NOT_FOUND)
async def update_product(
    body: ProductWrite,
    row: Annotated[ProductRow, Depends(owned_product)],
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Product:
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    audit(db, principal, "product.update", f"product:{row.id}", {"name": row.name})
    await db.commit()
    return Product.model_validate(row)


@router.delete(
    "/products/{product_id}",
    status_code=204,
    responses={
        **NOT_FOUND,
        409: {"model": ErrorBody, "description": "A document is still indexing"},
    },
)
async def delete_product(
    row: Annotated[ProductRow, Depends(owned_product)],
    principal: Annotated[Principal, Depends(get_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    qdrant: Annotated[AsyncQdrantClient, Depends(get_qdrant)],
    settings: Annotated[RetrievalSettings, Depends(get_retrieval_settings)],
) -> Response:
    documents = await db.scalars(
        select(DocumentRow).where(DocumentRow.product_id == row.id)
    )
    await remove_chunks(qdrant, settings, row.id, documents.all())
    audit(db, principal, "product.delete", f"product:{row.id}", {"name": row.name})
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)
