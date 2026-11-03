"use client";

import Link from "next/link";
import { useState } from "react";

import { ProductDocuments } from "@/components/product-documents";
import { ProductForm } from "@/components/product-form";
import { Button } from "@/components/ui/button";
import type { Product } from "@/lib/api/client";
import type { ProductLoad } from "@/lib/product";

const linkClass =
  "text-sm underline underline-offset-4 focus-visible:[outline:var(--hui-focus-ring)] focus-visible:outline-offset-[var(--hui-focus-ring-offset-accent)]";

export function ProductEditor({
  apiUrl,
  loaded,
}: {
  apiUrl: string;
  loaded: ProductLoad;
}) {
  const [product, setProduct] = useState<Product | null>(
    loaded.status === "ready" ? loaded.product : null,
  );
  const missing = loaded.status === "missing";
  const loadError = loaded.status === "error" ? loaded.message : null;

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-lg min-w-0 flex-col gap-8 px-6 py-16">
      <Link className={linkClass} href="/">
        New product
      </Link>
      {missing ? (
        <p className="text-pretty text-sm leading-6 text-foreground">Product not found.</p>
      ) : null}
      {loadError ? (
        <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
          {loadError}
        </p>
      ) : null}
      {product ? (
        <>
          <h1 className="text-balance text-2xl font-medium tracking-tight text-foreground [overflow-wrap:anywhere]">
            {product.name}
          </h1>
          <Button
            variant="outline"
            render={<Link href={`/products/${product.id}/session`} />}
          >
            Start session
          </Button>
          <ProductForm
            apiUrl={apiUrl}
            productId={product.id}
            initial={product}
            submitLabel="Save"
            formLabel="Product config"
            onSaved={setProduct}
          />
          <ProductDocuments apiUrl={apiUrl} productId={product.id} />
        </>
      ) : null}
    </main>
  );
}
