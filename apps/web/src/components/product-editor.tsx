"use client";

import Link from "next/link";
import { useState, type ChangeEvent, type FormEvent } from "react";

import { ProductForm } from "@/components/product-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiPath, errorDetail, readJson } from "@/lib/api";
import { indexedLabel, type Product, type ProductLoad } from "@/lib/product";

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
      {missing ? <p className="text-sm text-foreground">Product not found.</p> : null}
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
          <ProductForm
            apiUrl={apiUrl}
            productId={product.id}
            initial={product}
            submitLabel="Save"
            formLabel="Product config"
            onSaved={setProduct}
          />
          <UploadDocuments apiUrl={apiUrl} productId={product.id} />
        </>
      ) : null}
    </main>
  );
}

function UploadDocuments({
  apiUrl,
  productId,
}: {
  apiUrl: string;
  productId: string;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function onFiles(event: ChangeEvent<HTMLInputElement>) {
    setFiles(event.target.files ? Array.from(event.target.files) : []);
    setMessage(null);
    setError(null);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setMessage(null);
    const body = new FormData();
    for (const file of files) {
      body.append("files", file);
    }
    try {
      const response = await fetch(
        apiPath(apiUrl, `/products/${productId}/documents`),
        { method: "POST", body },
      );
      const payload = (await readJson(response)) as {
        status?: string;
        chunk_count?: number;
        error?: string | null;
      } | null;
      if (!response.ok) {
        setError(errorDetail(payload, "Could not upload documents."));
        return;
      }
      if (payload?.status === "failed") {
        setError(payload.error || "Upload failed.");
        return;
      }
      if (payload?.status !== "indexed" || typeof payload.chunk_count !== "number") {
        setError("Could not upload documents.");
        return;
      }
      setMessage(indexedLabel(payload.chunk_count));
    } catch {
      setError("Could not upload documents.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form
      aria-label="Upload documents"
      className="flex min-w-0 flex-col gap-4"
      onSubmit={onSubmit}
    >
      <h2 className="text-balance text-sm font-medium text-foreground">Documents</h2>
      <div className="flex min-w-0 flex-col gap-2">
        <label htmlFor="document-files" className="text-sm font-medium text-foreground">
          Files
        </label>
        <p id="document-files-hint" className="text-pretty text-sm leading-6 text-muted-foreground">
          Markdown, HTML, text, or PDF.
        </p>
        <Input
          id="document-files"
          name="files"
          type="file"
          multiple
          accept=".md,.markdown,.txt,.html,.htm,.pdf"
          aria-describedby="document-files-hint"
          onChange={onFiles}
        />
      </div>
      {message ? (
        <p role="status" className="text-sm text-foreground tabular-nums">
          {message}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
          {error}
        </p>
      ) : null}
      <Button type="submit" disabled={pending || files.length === 0}>
        Upload documents
      </Button>
    </form>
  );
}
