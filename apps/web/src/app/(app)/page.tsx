import { connection } from "next/server";
import { Suspense } from "react";

import { HomePage, type HomeData } from "@/components/home-page";
import { publicApiUrl } from "@/lib/api/client";
import { serverApi } from "@/lib/api/server";

export default function Page() {
  return (
    <Suspense fallback={<HomePage apiUrl={publicApiUrl()} />}>
      <HomeRoute />
    </Suspense>
  );
}

async function HomeRoute() {
  return <HomePage apiUrl={publicApiUrl()} data={await loadHome()} />;
}

// ponytail: one documents request per product; add counts to GET /products
// if an org grows past a few dozen products.
async function loadHome(): Promise<HomeData | null> {
  // The API client draws a random request id, which a prerender may not do.
  await connection();
  try {
    const api = await serverApi();
    const [products, sessions] = await Promise.all([api.GET("/products"), api.GET("/sessions")]);
    if (!products.data || !sessions.data) {
      return null;
    }
    const documents = await Promise.all(
      products.data.map((product) =>
        api
          .GET("/products/{product_id}/documents", { params: { path: { product_id: product.id } } })
          .then(({ data }) => data),
      ),
    );
    if (!documents.every((list) => list !== undefined)) {
      return null;
    }
    return {
      products: products.data,
      documentCounts: Object.fromEntries(
        products.data.map((product, index) => [product.id, documents[index].length]),
      ),
      sessions: sessions.data,
    };
  } catch {
    return null;
  }
}
