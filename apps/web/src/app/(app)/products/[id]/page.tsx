import { connection } from "next/server";
import { Suspense } from "react";

import { ProductEditor } from "@/components/product-editor";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { publicApiUrl } from "@/lib/api/client";
import { loadProduct } from "@/lib/api/server";

export default function Page({ params }: PageProps<"/products/[id]">) {
  return (
    <Suspense fallback={<ProductSkeleton />}>
      <ProductRoute params={params} />
    </Suspense>
  );
}

function ProductSkeleton() {
  return (
    <main className="mx-auto flex w-full max-w-[1080px] min-w-0 flex-col gap-8 px-4 py-8 sm:gap-12 sm:px-8 sm:py-12">
      <Loading label="Loading the product" className="flex min-w-0 flex-col gap-8 sm:gap-12">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-4">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-9 w-64 max-w-full" />
            <Skeleton className="h-4 w-96 max-w-full" />
          </div>
          <Skeleton className="h-10 w-36 rounded-control" />
        </div>
        <div className="grid gap-10 sm:gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,21rem)]">
          <div className="flex flex-col gap-4">
            <Skeleton className="h-5 w-28" />
            <Skeleton className="h-24 rounded-card" />
            <Skeleton className="h-64 rounded-card" />
          </div>
          <Skeleton className="h-96 rounded-card" />
        </div>
      </Loading>
    </main>
  );
}

async function ProductRoute({
  params,
}: Pick<PageProps<"/products/[id]">, "params">) {
  const { id } = await params;
  // The API client tags each request with Math.random, so render per request.
  await connection();
  const loaded = await loadProduct(id);
  return <ProductEditor apiUrl={publicApiUrl()} loaded={loaded} />;
}
