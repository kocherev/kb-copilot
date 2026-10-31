"""Product configuration stored in Postgres."""

from typing import Protocol
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from pydantic import BaseModel

from kb_api.settings import load_settings

router = APIRouter()


class ProductWrite(BaseModel):
    name: str
    description: str
    tone: str
    refusal_rules: str


class Product(ProductWrite):
    id: str


def clean_config(payload: ProductWrite) -> ProductWrite:
    return ProductWrite(
        name=_text(payload.name, "name", 120, "name must be one line"),
        description=_text(
            payload.description,
            "description",
            2000,
            "description must be one paragraph",
        ),
        tone=_text(payload.tone, "tone", 200, "tone must be one line"),
        refusal_rules=_text(payload.refusal_rules, "refusal rules", 4000, None),
    )


def _text(value: str, label: str, limit: int, line_error: str | None) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > limit:
        raise ValueError(f"{label} must be 1 to {limit} characters")
    if line_error is not None and any(character in cleaned for character in "\r\n"):
        raise ValueError(line_error)
    return cleaned


def require_config(payload: ProductWrite) -> ProductWrite:
    try:
        return clean_config(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    tone TEXT NOT NULL,
    refusal_rules TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


class ProductStore(Protocol):
    def ensure_schema(self) -> None: ...

    def create(self, product: Product) -> None: ...

    def save(self, product: Product) -> bool: ...

    def get(self, product_id: str) -> Product | None: ...


class MemoryProductStore:
    def __init__(self) -> None:
        self.products: dict[str, Product] = {}

    def ensure_schema(self) -> None:
        return

    def create(self, product: Product) -> None:
        self.products[product.id] = product.model_copy()

    def save(self, product: Product) -> bool:
        if product.id not in self.products:
            return False
        self.products[product.id] = product.model_copy()
        return True

    def get(self, product_id: str) -> Product | None:
        found = self.products.get(product_id)
        if found is None:
            return None
        return found.model_copy()


class PostgresProductStore:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ready = False

    def _connect(self) -> Connection:
        return Connection.connect(self._database_url)

    def ensure_schema(self) -> None:
        if self._ready:
            return
        with self._connect() as connection:
            connection.execute(_SCHEMA)
        self._ready = True

    def create(self, product: Product) -> None:
        self.ensure_schema()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO products (
                    id, name, description, tone, refusal_rules
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    product.id,
                    product.name,
                    product.description,
                    product.tone,
                    product.refusal_rules,
                ),
            )

    def save(self, product: Product) -> bool:
        self.ensure_schema()
        with self._connect() as connection:
            updated = connection.execute(
                """
                UPDATE products
                SET name = %s,
                    description = %s,
                    tone = %s,
                    refusal_rules = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                (
                    product.name,
                    product.description,
                    product.tone,
                    product.refusal_rules,
                    product.id,
                ),
            )
            return updated.rowcount == 1

    def get(self, product_id: str) -> Product | None:
        self.ensure_schema()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, name, description, tone, refusal_rules
                FROM products
                WHERE id = %s
                """,
                (product_id,),
            ).fetchone()
        if row is None:
            return None
        found_id, name, description, tone, refusal_rules = row
        return Product(
            id=found_id,
            name=name,
            description=description,
            tone=tone,
            refusal_rules=refusal_rules,
        )


def get_product_store() -> ProductStore:
    store = PostgresProductStore(load_settings().database_url)
    store.ensure_schema()
    return store


def _product_from(config: ProductWrite, product_id: str) -> Product:
    return Product(
        id=product_id,
        name=config.name,
        description=config.description,
        tone=config.tone,
        refusal_rules=config.refusal_rules,
    )


@router.post("/products", status_code=201)
def create_product(
    body: ProductWrite,
    store: ProductStore = Depends(get_product_store),
) -> Product:
    product = _product_from(require_config(body), str(uuid4()))
    store.create(product)
    return product


@router.get("/products/{product_id}")
def read_product(
    product_id: UUID,
    store: ProductStore = Depends(get_product_store),
) -> Product:
    found = store.get(str(product_id))
    if found is None:
        raise HTTPException(status_code=404, detail="product not found")
    return found


@router.put("/products/{product_id}")
def update_product(
    product_id: UUID,
    body: ProductWrite,
    store: ProductStore = Depends(get_product_store),
) -> Product:
    product = _product_from(require_config(body), str(product_id))
    if not store.save(product):
        raise HTTPException(status_code=404, detail="product not found")
    return product
