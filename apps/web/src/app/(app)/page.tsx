import { Suspense } from "react";

import { HomePage } from "@/components/home-page";
import { publicApiUrl } from "@/lib/api/client";
import { loadProducts } from "@/lib/api/server";

export default function Page() {
  return (
    <Suspense
      fallback={
        <main className="mx-auto flex min-h-dvh w-full max-w-lg flex-col px-6 py-16 text-sm leading-6 text-muted-foreground">
          Loading products.
        </main>
      }
    >
      <HomeRoute />
    </Suspense>
  );
}

async function HomeRoute() {
  return <HomePage apiUrl={publicApiUrl()} products={await loadProducts()} />;
}
