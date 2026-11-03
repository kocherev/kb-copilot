import Link from "next/link";
import { Suspense } from "react";

import { SessionReplay } from "@/components/session-replay";
import { loadProduct, loadReplay } from "@/lib/api/server";

const linkClass =
  "text-sm underline underline-offset-4 focus-visible:[outline:var(--hui-focus-ring)] focus-visible:outline-offset-[var(--hui-focus-ring-offset-accent)]";

export default function Page({
  params,
}: PageProps<"/products/[id]/sessions/[sessionId]">) {
  return (
    <Suspense
      fallback={
        <main className="mx-auto flex min-h-dvh w-full max-w-2xl flex-col px-6 py-16 text-sm leading-6 text-muted-foreground">
          Loading session.
        </main>
      }
    >
      <ReplayRoute params={params} />
    </Suspense>
  );
}

async function ReplayRoute({
  params,
}: Pick<PageProps<"/products/[id]/sessions/[sessionId]">, "params">) {
  const { id, sessionId } = await params;
  const [product, loaded] = await Promise.all([loadProduct(id), loadReplay(sessionId)]);
  if (
    product.status !== "ready" ||
    loaded.status !== "ready" ||
    loaded.replay.product_id !== product.product.id
  ) {
    const message =
      product.status === "error"
        ? product.message
        : loaded.status === "error"
          ? loaded.message
          : "Session not found.";
    return (
      <main className="mx-auto flex min-h-dvh w-full max-w-2xl min-w-0 flex-col gap-8 px-6 py-16">
        <Link className={linkClass} href={`/products/${id}`}>
          Product
        </Link>
        <p className="text-pretty text-sm leading-6 text-foreground">{message}</p>
      </main>
    );
  }
  return (
    <SessionReplay
      replay={loaded.replay}
      productId={product.product.id}
      productName={product.product.name}
      agentName={product.product.agent_name}
    />
  );
}
