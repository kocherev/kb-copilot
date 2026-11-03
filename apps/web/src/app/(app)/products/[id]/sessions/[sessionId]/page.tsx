import { SearchX } from "lucide-react";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { SessionReplay } from "@/components/session-replay";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { loadProduct, loadReplay } from "@/lib/api/server";

const frame = "mx-auto flex w-full max-w-[1080px] min-w-0 flex-col gap-8 px-4 py-8 sm:gap-10 sm:px-8 sm:py-12";

export default function Page({
  params,
}: PageProps<"/products/[id]/sessions/[sessionId]">) {
  return (
    <Suspense fallback={<ReplaySkeleton />}>
      <ReplayRoute params={params} />
    </Suspense>
  );
}

function ReplaySkeleton() {
  return (
    <main className={frame}>
      <Loading label="Loading the replay" className="flex min-w-0 flex-col gap-8 sm:gap-10">
        <div className="flex flex-col gap-4">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-9 w-72 max-w-full" />
          <Skeleton className="h-4 w-80 max-w-full" />
        </div>
        <Skeleton className="h-24 rounded-card" />
        <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)] lg:gap-12">
          <div className="flex flex-col gap-7">
            {[0, 1, 2, 3].map((row) => (
              <div key={row} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-x-4">
                <Skeleton className="size-8 rounded-full" />
                <div className="flex flex-col gap-2 pt-1">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-2/3" />
                </div>
              </div>
            ))}
          </div>
          <Skeleton className="h-80 rounded-card" />
        </div>
      </Loading>
    </main>
  );
}

async function ReplayRoute({
  params,
}: Pick<PageProps<"/products/[id]/sessions/[sessionId]">, "params">) {
  const { id, sessionId } = await params;
  // The API client tags each request with Math.random, so render per request.
  await connection();
  const [product, loaded] = await Promise.all([loadProduct(id), loadReplay(sessionId)]);
  if (
    product.status === "ready" &&
    loaded.status === "ready" &&
    loaded.replay.product_id === product.product.id
  ) {
    return (
      <SessionReplay
        replay={loaded.replay}
        productId={product.product.id}
        productName={product.product.name}
        agentName={product.product.agent_name}
      />
    );
  }
  const failed = product.status === "error" ? product : loaded.status === "error" ? loaded : null;
  const back =
    product.status === "ready"
      ? { href: `/products/${product.product.id}`, label: `Back to ${product.product.name}` }
      : { href: "/", label: "All products" };
  return (
    <main className={frame}>
      <EmptyState
        icon={SearchX}
        title={failed ? "Couldn’t load this session" : "Session not found"}
        description={
          failed
            ? `${failed.message} Check the API is running, then try again.`
            : "It may belong to another product, or the link is wrong."
        }
        action={
          <>
            {failed ? (
              <Button render={<a href={`/products/${id}/sessions/${sessionId}`} />}>Try again</Button>
            ) : null}
            <Button variant="outline" render={<Link href={back.href} />}>
              {back.label}
            </Button>
          </>
        }
      />
    </main>
  );
}
