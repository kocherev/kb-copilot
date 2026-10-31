import { Suspense } from "react";

import { ProductEditor } from "@/components/product-editor";
import { apiPath, readJson } from "@/lib/api";
import { productFromResponse, type ProductLoad } from "@/lib/product";

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
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const loaded = await loadProduct(apiUrl, id);
  return <ProductEditor apiUrl={apiUrl} loaded={loaded} />;
}

async function loadProduct(apiUrl: string, id: string): Promise<ProductLoad> {
  try {
    const response = await fetch(apiPath(apiUrl, `/products/${id}`));
    return productFromResponse(response.status, await readJson(response));
  } catch {
    return { status: "error", message: "Could not load the product." };
  }
}
