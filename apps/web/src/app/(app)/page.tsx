import { Suspense } from "react";

import { HomePage } from "@/components/home-page";
import { publicApiUrl } from "@/lib/api/client";
import { loadProducts } from "@/lib/api/server";

export default function Page() {
  return (
    <Suspense fallback={<HomePage apiUrl={publicApiUrl()} />}>
      <HomeRoute />
    </Suspense>
  );
}

async function HomeRoute() {
  return <HomePage apiUrl={publicApiUrl()} products={await loadProducts()} />;
}
