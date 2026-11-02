import Link from "next/link";
import { Suspense } from "react";

import { SessionView } from "@/components/session-view";
import { loadProduct, publicApiUrl } from "@/lib/api";

export default function Page({
  params,
}: PageProps<"/products/[id]/session">) {
  return (
    <Suspense
      fallback={
        <main className="mx-auto flex min-h-dvh w-full max-w-lg flex-col px-6 py-16 text-sm leading-6 text-muted-foreground">
          Loading session.
        </main>
      }
    >
      <SessionRoute params={params} />
    </Suspense>
  );
}

async function SessionRoute({
  params,
}: Pick<PageProps<"/products/[id]/session">, "params">) {
  const { id } = await params;
  const loaded = await loadProduct(id);
  if (loaded.status !== "ready") {
    return (
      <main className="mx-auto flex min-h-dvh w-full max-w-lg min-w-0 flex-col gap-8 px-6 py-16">
        <Link
          className="text-sm underline underline-offset-4 focus-visible:[outline:var(--hui-focus-ring)] focus-visible:outline-offset-[var(--hui-focus-ring-offset-accent)]"
          href="/"
        >
          New product
        </Link>
        <p className="text-pretty text-sm leading-6 text-foreground">
          {loaded.status === "missing" ? "Product not found." : loaded.message}
        </p>
      </main>
    );
  }
  return (
    <SessionView
      apiUrl={publicApiUrl()}
      productId={loaded.product.id}
      productName={loaded.product.name}
    />
  );
}
