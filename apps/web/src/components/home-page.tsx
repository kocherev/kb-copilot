import Link from "next/link";

import { ProductForm } from "@/components/product-form";
import type { Product } from "@/lib/api/client";

const linkClass =
  "text-sm underline underline-offset-4 [overflow-wrap:anywhere] focus-visible:[outline:var(--hui-focus-ring)] focus-visible:outline-offset-[var(--hui-focus-ring-offset-accent)]";

export function HomePage({
  apiUrl,
  products,
}: {
  apiUrl: string;
  products: Product[] | null;
}) {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-lg min-w-0 flex-col gap-8 px-6 py-16">
      <div className="flex flex-col gap-3">
        <h1 className="text-balance text-2xl font-medium tracking-tight text-foreground">
          Knowledge base copilot
        </h1>
        <p className="text-pretty text-sm leading-6 text-muted-foreground">
          Create a product, set how the agent should sound, and upload the
          documents it can answer from.
        </p>
        <p className="text-pretty text-sm leading-6 text-muted-foreground">
          Open a product and start a session. The browser joins with your
          microphone and screen, and the agent answers by voice.
        </p>
      </div>
      <section aria-label="Products" className="flex min-w-0 flex-col gap-3">
        <h2 className="text-sm font-medium text-foreground">Products</h2>
        {products === null ? (
          <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
            Could not load products.
          </p>
        ) : products.length === 0 ? (
          <p className="text-sm leading-6 text-muted-foreground">No products yet.</p>
        ) : (
          <ul className="flex min-w-0 list-none flex-col gap-2 p-0">
            {products.map((product) => (
              <li key={product.id}>
                <Link className={linkClass} href={`/products/${product.id}`}>
                  {product.name}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
      <ProductForm
        apiUrl={apiUrl}
        submitLabel="Create product"
        formLabel="Create product"
      />
    </main>
  );
}
