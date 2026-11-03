"use client";

import { Dialog } from "@base-ui/react/dialog";
import { Boxes, Clock, FileText, Plus, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { ProductForm } from "@/components/product-form";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { InlineError } from "@/components/ui/inline-error";
import { PageHeader } from "@/components/ui/page-header";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import type { Product, SessionSummary } from "@/lib/api/client";
import { stagger } from "@/lib/motion";

export type HomeData = {
  products: Product[];
  documentCounts: Record<string, number>;
  sessions: SessionSummary[];
};

function lastSessionAt(sessions: SessionSummary[], productId: string): string | null {
  let latest: string | null = null;
  for (const session of sessions) {
    if (
      session.product_id === productId &&
      (latest === null || Date.parse(session.created_at) > Date.parse(latest))
    ) {
      latest = session.created_at;
    }
  }
  return latest;
}

// UTC, so the server render and hydration print the same day.
const day = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  timeZone: "UTC",
});

// `data` is undefined while the list loads and null when it failed.
export function HomePage({ apiUrl, data }: { apiUrl: string; data?: HomeData | null }) {
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [retrying, startRetry] = useTransition();

  return (
    <Dialog.Root open={creating} onOpenChange={setCreating}>
      <main className="mx-auto flex w-full max-w-[1080px] min-w-0 flex-col gap-8 px-4 py-10 sm:gap-10 sm:px-8 sm:py-14">
        <PageHeader
          title="Products"
          description="Upload a product’s help docs, then talk to its voice agent. It answers out loud, sees your shared screen and cites the page behind each answer."
          actions={data?.products.length === 0 ? null : <NewProductButton />}
        />
        <section aria-label="Products" className="min-w-0">
          {data === undefined || retrying ? (
            <ProductGridSkeleton />
          ) : data === null ? (
            <InlineError onRetry={() => startRetry(() => router.refresh())}>
              Couldn’t load your products. Check that the API is running, then try again.
            </InlineError>
          ) : data.products.length === 0 ? (
            <EmptyState
              icon={Boxes}
              title="Set up your first product"
              description="Name it, choose how its agent sounds, then upload the help docs the agent answers from."
              action={<NewProductButton />}
            />
          ) : (
            <ul className="grid min-w-0 list-none grid-cols-1 gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
              {data.products.map((product, index) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  documentCount={data.documentCounts[product.id] ?? 0}
                  lastSession={lastSessionAt(data.sessions, product.id)}
                  index={index}
                />
              ))}
            </ul>
          )}
        </section>
      </main>
      <Dialog.Portal keepMounted>
        <Dialog.Backdrop className="fixed inset-0 z-(--z-overlay) bg-foreground/20 transition-opacity duration-(--duration-slow) ease-out data-ending-style:duration-(--duration-fast) data-starting-style:opacity-0 data-ending-style:opacity-0 dark:bg-black/50" />
        <Dialog.Popup className="fixed inset-x-0 bottom-0 z-(--z-overlay) flex max-h-[92dvh] min-w-0 flex-col overflow-hidden rounded-t-panel bg-surface shadow-float outline-none transition-[translate,opacity] duration-(--duration-slow) ease-drawer data-ending-style:duration-(--duration-fast) data-ending-style:ease-out data-starting-style:translate-y-[calc(var(--motion-y)*4)] data-starting-style:opacity-0 data-ending-style:translate-y-[calc(var(--motion-y)*2)] data-ending-style:opacity-0 sm:inset-y-2 sm:right-2 sm:left-auto sm:max-h-none sm:w-[460px] sm:rounded-panel sm:data-starting-style:translate-x-[calc(var(--motion-y)*4)] sm:data-starting-style:translate-y-0 sm:data-ending-style:translate-x-[calc(var(--motion-y)*2)] sm:data-ending-style:translate-y-0">
          <div className="flex min-w-0 items-start justify-between gap-4 border-b border-border px-5 py-4">
            <div className="flex min-w-0 flex-col gap-1">
              <Dialog.Title className="text-heading text-foreground">New product</Dialog.Title>
              <Dialog.Description className="text-meta text-pretty text-muted-foreground">
                You can change any of this later.
              </Dialog.Description>
            </div>
            <Dialog.Close
              aria-label="Close"
              className="-mr-1.5 grid size-8 shrink-0 cursor-pointer place-items-center rounded-full text-muted-foreground transition-colors duration-150 ease-out outline-none hover:bg-surface-hover hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring pointer-coarse:size-10"
            >
              <X aria-hidden className="size-4" />
            </Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pt-5 pb-6">
            <ProductForm
              apiUrl={apiUrl}
              submitLabel="Create product"
              formLabel="Create product"
              onSaved={(product) => {
                setCreating(false);
                router.push(`/products/${product.id}`);
              }}
            />
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function NewProductButton() {
  return (
    <Dialog.Trigger render={<Button className="pr-4 pl-3.5" />}>
      <Plus aria-hidden />
      New product
    </Dialog.Trigger>
  );
}

function ProductCard({
  product,
  documentCount,
  lastSession,
  index,
}: {
  product: Product;
  documentCount: number;
  lastSession: string | null;
  index: number;
}) {
  return (
    <li
      style={stagger(index)}
      className="group relative flex min-w-0 animate-enter flex-col gap-4 rounded-card border border-transparent bg-surface p-5 shadow-soft transition-shadow duration-150 ease-out hover:shadow-float has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-ring"
    >
      <div className="flex min-w-0 items-center gap-2.5">
        <span
          aria-hidden
          className="grid size-8 shrink-0 place-items-center rounded-full bg-primary-soft text-sm font-semibold text-primary-soft-foreground"
        >
          {product.agent_name.slice(0, 1).toUpperCase()}
        </span>
        <p className="min-w-0 truncate text-meta text-muted-foreground">
          {product.agent_name}, {product.voice} voice
        </p>
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <h2 className="text-heading text-balance text-foreground [overflow-wrap:anywhere]">
          <Link
            href={`/products/${product.id}`}
            className="outline-none after:absolute after:inset-0 after:rounded-card"
          >
            {product.name}
          </Link>
        </h2>
        <p className="line-clamp-2 text-meta text-pretty text-muted-foreground [overflow-wrap:anywhere]">
          {product.description}
        </p>
      </div>
      <dl className="flex min-w-0 flex-wrap gap-x-4 gap-y-1 border-t border-border pt-3.5 text-meta text-muted-foreground tabular-nums">
        <div>
          <dt className="sr-only">Documents</dt>
          <dd className="flex items-center gap-1.5">
            <FileText aria-hidden className="size-3.5" />
            {documentCount === 0
              ? "No documents yet"
              : documentCount === 1
                ? "1 document"
                : `${documentCount} documents`}
          </dd>
        </div>
        <div>
          <dt className="sr-only">Last session</dt>
          <dd className="flex items-center gap-1.5">
            <Clock aria-hidden className="size-3.5" />
            {lastSession === null ? (
              "No sessions yet"
            ) : (
              <time dateTime={lastSession}>Last session {day.format(new Date(lastSession))}</time>
            )}
          </dd>
        </div>
      </dl>
    </li>
  );
}

function ProductGridSkeleton() {
  return (
    <Loading label="Loading products" className="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {[0, 1, 2].map((key) => (
        <div
          key={key}
          className="flex min-w-0 flex-col gap-4 rounded-card border border-transparent bg-surface p-5 shadow-soft"
        >
          <div className="flex items-center gap-2.5">
            <Skeleton className="size-8 rounded-full" />
            <Skeleton className="h-3.5 w-28" />
          </div>
          <div className="flex flex-col gap-2">
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="h-3.5 w-full" />
            <Skeleton className="h-3.5 w-4/5" />
          </div>
          <Skeleton className="mt-1 h-3.5 w-1/2" />
        </div>
      ))}
    </Loading>
  );
}
