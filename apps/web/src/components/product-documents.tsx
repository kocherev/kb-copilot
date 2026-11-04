"use client";

import {
  CircleAlert,
  CircleCheck,
  Clock,
  CloudUpload,
  FileCode,
  FileText,
  FileType,
  LoaderCircle,
  Trash2,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  startTransition,
  useCallback,
  useEffect,
  useRef,
  useState,
  ViewTransition,
  type ChangeEvent,
  type DragEvent,
} from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { InlineError } from "@/components/ui/inline-error";
import { Section } from "@/components/ui/section";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Surface } from "@/components/ui/surface";
import {
  apiPath,
  browserApi,
  browserToken,
  errorDetail,
  readJson,
} from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { stagger } from "@/lib/motion";
import { fileSize, indexedLabel } from "@/lib/product";
import { countLabel } from "@/lib/replay";
import { cn } from "@/lib/utils";

type ProductDocument = components["schemas"]["Document"];

const POLL_MS = 2000;
// How long a removed document can be brought back before it is deleted.
const UNDO_MS = 5000;
const ACCEPT = ".md,.markdown,.txt,.html,.htm,.pdf";

const STATUS: Record<
  ProductDocument["status"],
  { label: string; Icon: LucideIcon; className: string; spin?: boolean }
> = {
  queued: { label: "Queued", Icon: Clock, className: "bg-surface-sunken text-muted-foreground" },
  indexing: {
    label: "Indexing",
    Icon: LoaderCircle,
    className: "bg-primary-soft text-primary-soft-foreground",
    spin: true,
  },
  indexed: { label: "Indexed", Icon: CircleCheck, className: "bg-success-soft text-success" },
  failed: { label: "Failed", Icon: CircleAlert, className: "bg-destructive-soft text-destructive" },
};

function isPending(document: ProductDocument): boolean {
  return document.status === "queued" || document.status === "indexing";
}

function detail(document: ProductDocument): string {
  switch (document.status) {
    case "queued":
      return "Waiting for its turn";
    case "indexing":
      return "Splitting into sections";
    case "indexed":
      return indexedLabel(document.chunk_count);
    case "failed":
      return document.error ? `${document.error[0]?.toUpperCase()}${document.error.slice(1)}.` : "Couldn’t read this file.";
  }
}

function fileIcon(title: string): LucideIcon {
  if (/\.pdf$/i.test(title)) {
    return FileType;
  }
  return /\.html?$/i.test(title) ? FileCode : FileText;
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

async function deleteDocument(
  apiUrl: string,
  productId: string,
  document: ProductDocument,
): Promise<string | null> {
  const fallback = `Couldn’t delete ${document.title}. Try again.`;
  try {
    const { response, error } = await browserApi(apiUrl).DELETE(
      "/products/{product_id}/documents/{document_id}",
      { params: { path: { product_id: productId, document_id: document.id } } },
    );
    return response.ok ? null : errorDetail(error, fallback);
  } catch {
    return fallback;
  }
}

function StatusChip({ document }: { document: ProductDocument }) {
  const { label, Icon, className, spin } = STATUS[document.status];
  return (
    <span
      className={cn(
        "flex shrink-0 items-center gap-1 rounded-full py-0.5 pr-2 pl-1.5 text-meta font-medium transition-colors duration-200 ease-out",
        className,
      )}
    >
      {/* Keyed by status so the new icon fades and scales in when the status changes. */}
      <Icon
        key={document.status}
        aria-hidden
        className={cn(
          "size-3.5 transition-[opacity,scale,filter] duration-300 ease-[cubic-bezier(0.2,0,0,1)] starting:opacity-0 motion-safe:starting:scale-25 motion-safe:starting:blur-[4px]",
          spin && "motion-safe:animate-spin",
        )}
      />
      {label}
    </span>
  );
}

function DropZone({
  empty,
  agentName,
  onFiles,
}: {
  empty: boolean;
  agentName: string;
  onFiles: (files: File[]) => void;
}) {
  const [over, setOver] = useState(false);

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setOver(false);
    onFiles(Array.from(event.dataTransfer.files));
  }

  function onPick(event: ChangeEvent<HTMLInputElement>) {
    onFiles(event.target.files ? Array.from(event.target.files) : []);
    // Picking the same file again after removing it should still count.
    event.target.value = "";
  }

  const choose = (
    <label
      className={cn(
        buttonVariants({ variant: empty ? "default" : "outline" }),
        "has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring",
      )}
    >
      <input
        type="file"
        multiple
        accept={ACCEPT}
        className="sr-only"
        aria-describedby="knowledge-hint"
        onChange={onPick}
      />
      Choose files
    </label>
  );

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          setOver(false);
        }
      }}
      onDrop={onDrop}
      data-over={over || undefined}
      className={cn(
        "flex min-w-0 rounded-card border border-dashed border-border-strong bg-surface-sunken transition-[background-color,border-color] duration-150 ease-out data-over:border-primary data-over:bg-primary-soft",
        empty
          ? "flex-col items-center gap-3 px-6 py-10 text-center"
          : "flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3.5",
      )}
    >
      <span
        className={cn(
          "grid shrink-0 place-items-center rounded-full bg-primary-soft text-primary-soft-foreground",
          empty ? "size-10" : "size-8",
        )}
      >
        <CloudUpload aria-hidden className={empty ? "size-5" : "size-4"} />
      </span>
      {empty ? (
        <>
          <p className="font-display text-xl/tight text-balance text-foreground">No documents yet</p>
          <p className="max-w-[44ch] text-body text-pretty text-muted-foreground">
            Add your help docs so {agentName} can answer from them. Drop them here, or
          </p>
          {choose}
        </>
      ) : (
        <>
          <p className="min-w-0 flex-1 text-sm text-pretty text-muted-foreground">
            {over ? "Drop to add them" : "Drop more files here, or"}
          </p>
          {choose}
        </>
      )}
    </div>
  );
}

export function ProductDocuments({
  apiUrl,
  productId,
  agentName,
  className,
}: {
  apiUrl: string;
  productId: string;
  agentName: string;
  className?: string;
}) {
  const [documents, setDocuments] = useState<ProductDocument[] | null>(null);
  // Rows present on the first load enter one after another; later ones do not wait.
  const [firstIds, setFirstIds] = useState<ReadonlySet<string>>(new Set());
  const [loadError, setLoadError] = useState(false);
  const [chosen, setChosen] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [removed, setRemoved] = useState<ProductDocument | null>(null);
  const [deleting, setDeleting] = useState<ReadonlySet<string>>(new Set());
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const undo = useRef<{ document: ProductDocument; timer: ReturnType<typeof setTimeout> } | null>(
    null,
  );

  // A load can land after the list is gone, for example when the user leaves the page.
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const refresh = useCallback(
    () =>
      fetchDocuments(apiUrl, productId).then((data) => {
        if (!mounted.current) return data;
        setLoadError(data === null);
        if (data) {
          setDocuments(data);
          setFirstIds((ids) => (ids.size ? ids : new Set(data.map((document) => document.id))));
        }
        return data;
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

  // Leaving the page keeps the removal the user asked for.
  useEffect(
    () => () => {
      const pending = undo.current;
      if (pending) {
        clearTimeout(pending.timer);
        void deleteDocument(apiUrl, productId, pending.document);
      }
    },
    [apiUrl, productId],
  );

  function addFiles(files: File[]) {
    setUploadError(null);
    setChosen((current) => [
      ...current.filter((file) => !files.some((added) => added.name === file.name)),
      ...files,
    ]);
  }

  async function upload() {
    setUploading(true);
    setUploadError(null);
    const body = new FormData();
    for (const file of chosen) {
      body.append("files", file);
    }
    try {
      const response = await fetch(apiPath(apiUrl, `/products/${productId}/documents`), {
        method: "POST",
        headers: { authorization: `Bearer ${await browserToken()}` },
        body,
      });
      if (!response.ok) {
        setUploadError(
          errorDetail(await readJson(response), "Couldn’t upload the files. Try again."),
        );
        return;
      }
      const data = await fetchDocuments(apiUrl, productId);
      startTransition(() => {
        setChosen([]);
        if (data) {
          setDocuments(data);
        }
      });
    } catch {
      setUploadError("Couldn’t upload the files. Check your connection, then try again.");
    } finally {
      setUploading(false);
    }
  }

  async function commit(document: ProductDocument) {
    setDeleting((ids) => new Set(ids).add(document.id));
    const failure = await deleteDocument(apiUrl, productId, document);
    if (failure === null) {
      await refresh();
    } else {
      setDeleteError(failure);
    }
    startTransition(() =>
      setDeleting((ids) => {
        const next = new Set(ids);
        next.delete(document.id);
        return next;
      }),
    );
  }

  function finishRemoval() {
    const pending = undo.current;
    if (!pending) {
      return;
    }
    clearTimeout(pending.timer);
    undo.current = null;
    setRemoved(null);
    void commit(pending.document);
  }

  function remove(document: ProductDocument) {
    // One undo at a time: a second removal settles the first.
    finishRemoval();
    setDeleteError(null);
    undo.current = { document, timer: setTimeout(finishRemoval, UNDO_MS) };
    startTransition(() => setRemoved(document));
  }

  function restore() {
    const pending = undo.current;
    if (!pending) {
      return;
    }
    clearTimeout(pending.timer);
    undo.current = null;
    startTransition(() => setRemoved(null));
  }

  const shown = documents?.filter(
    (document) => document.id !== removed?.id && !deleting.has(document.id),
  );
  const failed = shown?.filter((d) => d.status === "failed").length ?? 0;
  const inProgress = shown?.filter(isPending).length ?? 0;
  const indexed = (shown?.length ?? 0) - failed - inProgress;

  return (
    <Section
      title="Knowledge"
      description={
        <span id="knowledge-hint">
          What {agentName} answers from. Markdown, HTML, text or PDF, up to 20 files of 2&nbsp;MB
          each. A file with the same name replaces the old one.
        </span>
      }
      className={className}
    >
      {documents === null && !loadError ? (
        <Loading label="Loading documents" className="flex flex-col gap-3">
          <Skeleton className="h-16 rounded-card" />
          <Surface padding="none" className="divide-y divide-border">
            {[0, 1, 2, 3].map((row) => (
              <div key={row} className="flex items-center gap-3 px-4 py-3">
                <Skeleton className="size-5 rounded-md" />
                <div className="flex flex-1 flex-col gap-1.5">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-3 w-24" />
                </div>
                <Skeleton className="h-5 w-16 rounded-full" />
              </div>
            ))}
          </Surface>
        </Loading>
      ) : null}
      {loadError ? (
        <InlineError onRetry={() => void refresh()}>
          Couldn&rsquo;t load documents. Check the API is running, then try again.
        </InlineError>
      ) : null}
      {documents !== null ? (
        <div className="flex min-w-0 flex-col gap-3">
          <DropZone empty={shown?.length === 0} agentName={agentName} onFiles={addFiles} />
          {chosen.length > 0 ? (
            <div className="flex min-w-0 flex-col gap-3 animate-enter">
              <ul aria-label="Files to upload" className="flex min-w-0 list-none flex-wrap gap-1.5 p-0">
                {chosen.map((file) => (
                  <li
                    key={file.name}
                    className="flex min-w-0 items-center gap-1.5 rounded-full bg-surface py-1 pr-1 pl-2.5 text-meta text-foreground shadow-ring"
                  >
                    <span className="min-w-0 truncate">{file.name}</span>
                    <span className="shrink-0 tabular-nums text-muted-foreground">
                      {fileSize(file.size)}
                    </span>
                    <button
                      type="button"
                      aria-label={`Remove ${file.name}`}
                      disabled={uploading}
                      onClick={() => setChosen((current) => current.filter((item) => item !== file))}
                      className="relative grid size-5 shrink-0 place-items-center rounded-full text-muted-foreground outline-none transition-colors duration-150 ease-out hover:bg-surface-hover hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50 pointer-coarse:after:absolute pointer-coarse:after:size-11"
                    >
                      <X aria-hidden className="size-3" />
                    </button>
                  </li>
                ))}
              </ul>
              <Button className="w-fit" disabled={uploading} onClick={() => void upload()}>
                {uploading ? <Spinner /> : null}
                {uploading
                  ? `Uploading ${countLabel(chosen.length, "file")}…`
                  : `Upload ${countLabel(chosen.length, "file")}`}
              </Button>
            </div>
          ) : null}
          {uploadError ? (
            <InlineError onRetry={() => void upload()}>{uploadError}</InlineError>
          ) : null}
          {deleteError ? <InlineError>{deleteError}</InlineError> : null}
          <div role="status" className="contents">
            {removed ? (
              <div
                key={removed.id}
                className="relative flex min-w-0 items-center gap-3 overflow-hidden rounded-control bg-surface py-1.5 pr-1.5 pl-3.5 text-sm text-foreground shadow-soft animate-enter"
              >
                <Trash2 aria-hidden className="size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">Removed {removed.title}.</span>
                <Button variant="ghost" size="sm" onClick={restore}>
                  Undo
                </Button>
                {/* How long is left to undo. Reduced motion keeps the button and drops the bar. */}
                <span
                  aria-hidden
                  style={{ transitionDuration: `${UNDO_MS}ms` }}
                  className="absolute inset-x-0 bottom-0 h-0.5 origin-left scale-x-0 bg-primary/60 transition-transform ease-linear starting:scale-x-100 motion-reduce:hidden"
                />
              </div>
            ) : null}
          </div>
          {shown && shown.length > 0 ? (
            <Surface padding="none">
              <div className="flex flex-col gap-2 border-b border-border px-4 py-3">
                <p role="status" className="text-meta tabular-nums text-muted-foreground">
                  {indexed} of {shown.length} indexed
                  {inProgress ? `, ${inProgress} in progress` : ""}
                  {failed ? `, ${failed} failed` : ""}.
                </p>
                {inProgress ? (
                  <span aria-hidden className="h-1 overflow-hidden rounded-full bg-surface-sunken">
                    <span
                      className="block h-full origin-left rounded-full bg-primary transition-transform duration-300 ease-out"
                      style={{ transform: `scaleX(${(indexed + failed) / shown.length})` }}
                    />
                  </span>
                ) : null}
              </div>
              <ul aria-label="Documents" className="flex min-w-0 list-none flex-col p-1.5">
                {shown.map((document, index) => {
                  const Icon = fileIcon(document.title);
                  return (
                    <ViewTransition key={document.id} enter="vt-rise" exit="vt-rise">
                      <li
                        style={firstIds.has(document.id) ? stagger(index) : undefined}
                        className={cn(
                          "flex min-w-0 items-center gap-3 rounded-control py-2 pr-1.5 pl-2.5 transition-colors duration-150 ease-out hover:bg-surface-hover",
                          firstIds.has(document.id) && "animate-enter",
                        )}
                      >
                        <Icon aria-hidden className="size-4 shrink-0 text-muted-foreground" />
                        <div className="flex min-w-0 flex-1 flex-col">
                          <p className="text-sm font-medium text-foreground [overflow-wrap:anywhere]">
                            {document.title}
                          </p>
                          <p
                            className={`text-meta text-pretty [overflow-wrap:anywhere] ${
                              document.status === "failed" ? "text-destructive" : "text-muted-foreground"
                            }`}
                          >
                            {detail(document)}
                          </p>
                        </div>
                        <StatusChip document={document} />
                        <Button
                          variant="link"
                          size="icon"
                          aria-label={`Delete ${document.title}`}
                          title={isPending(document) ? "Wait until indexing finishes" : "Delete"}
                          disabled={isPending(document)}
                          onClick={() => remove(document)}
                          className="text-muted-foreground not-disabled:hover:bg-destructive-soft not-disabled:hover:text-destructive"
                        >
                          <Trash2 aria-hidden />
                        </Button>
                      </li>
                    </ViewTransition>
                  );
                })}
              </ul>
            </Surface>
          ) : null}
        </div>
      ) : null}
    </Section>
  );
}
