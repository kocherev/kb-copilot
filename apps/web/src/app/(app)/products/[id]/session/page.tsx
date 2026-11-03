import { CircleAlert, SearchX } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { SessionView } from "@/components/session-view";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { publicApiUrl } from "@/lib/api/client";
import { loadProduct } from "@/lib/api/server";

const frame = "mx-auto flex w-full max-w-[640px] min-w-0 flex-col gap-8 px-4 py-8 sm:px-8 sm:py-12";

export default function Page({
  params,
}: PageProps<"/products/[id]/session">) {
  return (
    <Suspense
      fallback={
        <main className={frame}>
          <Loading label="Loading session" className="flex flex-col gap-8">
            <div className="flex flex-col gap-4">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="h-9 w-64 max-w-full" />
              <Skeleton className="h-5 w-full max-w-md" />
            </div>
            <Skeleton className="h-80 w-full rounded-card" />
          </Loading>
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
    const missing = loaded.status === "missing";
    return (
      <main className={frame}>
        <EmptyState
          icon={missing ? SearchX : CircleAlert}
          title={missing ? "Product not found" : "Couldn't load this product"}
          description={
            missing
              ? "It may have been deleted, or the link is wrong."
              : `${loaded.message} Check that the API is running, then try again.`
          }
          action={
            <>
              {missing ? null : (
                <Button render={<Link href={`/products/${id}/session`} />}>Try again</Button>
              )}
              <Button variant="outline" render={<Link href="/" />}>
                All products
              </Button>
            </>
          }
        />
      </main>
    );
  }
  return (
    <SessionView
      apiUrl={publicApiUrl()}
      productId={loaded.product.id}
      productName={loaded.product.name}
      agentName={loaded.product.agent_name}
    />
  );
}
