"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  apiPath,
  browserApi,
  browserToken,
  errorDetail,
  readJson,
} from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { indexedLabel } from "@/lib/product";

type ProductDocument = components["schemas"]["Document"];

const POLL_MS = 2000;

function isPending(document: ProductDocument): boolean {
  return document.status === "queued" || document.status === "indexing";
}

function statusLabel(document: ProductDocument): string {
  switch (document.status) {
    case "queued":
      return "Queued.";
    case "indexing":
      return "Indexing.";
    case "indexed":
      return indexedLabel(document.chunk_count);
    case "failed":
      return document.error ? `Failed: ${document.error}.` : "Failed.";
  }
}

async function fetchDocuments(
  apiUrl: string,
  productId: string,
): Promise<ProductDocument[] | null> {
  try {
    const { data } = await browserApi(apiUrl).GET("/products/{product_id}/documents", {
      params: { path: { product_id: productId } },
    });
    return data ?? null;
  } catch {
    return null;
  }
}

export function ProductDocuments({
  apiUrl,
  productId,
}: {
  apiUrl: string;
  productId: string;
}) {
  const [documents, setDocuments] = useState<ProductDocument[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useRef<HTMLFormElement>(null);

  const refresh = useCallback(
    () =>
      fetchDocuments(apiUrl, productId).then((data) => {
        setLoadError(data === null);
        if (data) {
          setDocuments(data);
        }
      }),
    [apiUrl, productId],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const unsettled = documents?.some(isPending) ?? false;
  useEffect(() => {
    if (!unsettled) {
      return;
    }
    const timer = setInterval(() => void refresh(), POLL_MS);
    return () => clearInterval(timer);
  }, [unsettled, refresh]);

  function onFiles(event: ChangeEvent<HTMLInputElement>) {
    setFiles(event.target.files ? Array.from(event.target.files) : []);
    setError(null);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    const body = new FormData();
    for (const file of files) {
      body.append("files", file);
    }
    try {
      const response = await fetch(
        apiPath(apiUrl, `/products/${productId}/documents`),
        {
          method: "POST",
          headers: { authorization: `Bearer ${await browserToken()}` },
          body,
        },
      );
      if (!response.ok) {
        setError(errorDetail(await readJson(response), "Could not upload documents."));
        return;
      }
      form.current?.reset();
      setFiles([]);
      await refresh();
    } catch {
      setError("Could not upload documents.");
    } finally {
      setPending(false);
    }
  }

  async function onDelete(document: ProductDocument) {
    setError(null);
    try {
      const { response, error: detail } = await browserApi(apiUrl).DELETE(
        "/products/{product_id}/documents/{document_id}",
        { params: { path: { product_id: productId, document_id: document.id } } },
      );
      if (!response.ok) {
        setError(errorDetail(detail, `Could not delete ${document.title}.`));
        return;
      }
      await refresh();
    } catch {
      setError(`Could not delete ${document.title}.`);
    }
  }

  const failed = documents?.filter((d) => d.status === "failed").length ?? 0;
  const inProgress = documents?.filter(isPending).length ?? 0;

  return (
    <section aria-labelledby="documents-heading" className="flex min-w-0 flex-col gap-4">
      <h2 id="documents-heading" className="text-balance text-sm font-medium text-foreground">
        Documents
      </h2>
      <form
        ref={form}
        aria-label="Upload documents"
        className="flex min-w-0 flex-col gap-4"
        onSubmit={onSubmit}
      >
        <div className="flex min-w-0 flex-col gap-2">
          <label htmlFor="document-files" className="text-sm font-medium text-foreground">
            Files
          </label>
          <p id="document-files-hint" className="text-pretty text-sm leading-6 text-muted-foreground">
            Markdown, HTML, text, or PDF. Up to 20 files, 2 MB each. A file with the same name replaces the old one.
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
        <Button type="submit" disabled={pending || files.length === 0}>
          Upload documents
        </Button>
      </form>
      {error ? (
        <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
          {error}
        </p>
      ) : null}
      {loadError ? (
        <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
          Could not load documents.
        </p>
      ) : null}
      {documents === null && !loadError ? (
        <p className="text-sm leading-6 text-muted-foreground">Loading documents.</p>
      ) : null}
      {documents?.length === 0 ? (
        <p className="text-sm leading-6 text-muted-foreground">No documents yet.</p>
      ) : null}
      {documents && documents.length > 0 ? (
        <>
          <p role="status" className="text-sm text-muted-foreground tabular-nums">
            {documents.length - inProgress - failed} indexed, {inProgress} in progress, {failed} failed.
          </p>
          <ul aria-label="Documents" className="flex min-w-0 flex-col gap-3">
            {documents.map((document) => (
              <li key={document.id} className="flex min-w-0 items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground [overflow-wrap:anywhere]">
                    {document.title}
                  </p>
                  <p className="text-pretty text-sm leading-6 text-muted-foreground">
                    {statusLabel(document)}
                  </p>
                </div>
                <Button
                  variant="outline"
                  aria-label={`Delete ${document.title}`}
                  disabled={isPending(document)}
                  onClick={() => void onDelete(document)}
                >
                  Delete
                </Button>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
