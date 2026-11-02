import { Suspense } from "react";

import { ProductEditor } from "@/components/product-editor";
import { publicApiUrl } from "@/lib/api/client";
import { loadProduct } from "@/lib/api/server";

export default function Page({ params }: PageProps<"/products/[id]">) {
  return (
    <Suspense
      fallback={
        <main className="mx-auto flex min-h-dvh w-full max-w-lg flex-col px-6 py-16 text-sm leading-6 text-muted-foreground">
          Loading product.
        </main>
      }
    >
      <ProductRoute params={params} />
    </Suspense>
  );
}

async function ProductRoute({
  params,
}: Pick<PageProps<"/products/[id]">, "params">) {
  const { id } = await params;
  const loaded = await loadProduct(id);
  return <ProductEditor apiUrl={publicApiUrl()} loaded={loaded} />;
}
