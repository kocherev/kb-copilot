"use client";

import { AudioLines, PackageSearch } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ProductDocuments } from "@/components/product-documents";
import { ProductForm } from "@/components/product-form";
import { ProductSessions } from "@/components/product-sessions";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { InlineError } from "@/components/ui/inline-error";
import { PageHeader } from "@/components/ui/page-header";
import { Section } from "@/components/ui/section";
import { Surface } from "@/components/ui/surface";
import type { Product } from "@/lib/api/client";
import type { ProductLoad } from "@/lib/product";

const productFrame =
  "mx-auto flex w-full max-w-[1080px] min-w-0 flex-col gap-8 px-4 py-8 sm:gap-12 sm:px-8 sm:py-12";

const allProducts = { href: "/", label: "All products" };

export function ProductEditor({
  apiUrl,
  loaded,
}: {
  apiUrl: string;
  loaded: ProductLoad;
}) {
  const [product, setProduct] = useState<Product | null>(
    loaded.status === "ready" ? loaded.product : null,
  );

  if (!product) {
    return (
      <main className={productFrame}>
        {loaded.status === "error" ? (
          <>
            <PageHeader title="Product" back={allProducts} />
            <InlineError onRetry={() => window.location.reload()}>
              {loaded.message} Check the API is running, then try again.
            </InlineError>
          </>
        ) : (
          <EmptyState
            icon={PackageSearch}
            title="Product not found"
            description="It may have been deleted, or the link is wrong."
            action={
              <Button variant="outline" render={<Link href="/" />}>
                All products
              </Button>
            }
          />
        )}
      </main>
    );
  }

  return (
    <main className={productFrame}>
      <PageHeader
        title={product.name}
        back={allProducts}
        description={<span className="line-clamp-2">{product.description}</span>}
        actions={
          <Button size="lg" render={<Link href={`/products/${product.id}/session`} />}>
            <AudioLines aria-hidden />
            Start session
          </Button>
        }
      />
      <div className="grid min-w-0 gap-10 sm:gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,21rem)] lg:grid-rows-[auto_1fr] lg:items-start">
        <ProductDocuments
          apiUrl={apiUrl}
          productId={product.id}
          agentName={product.agent_name}
          className="lg:col-start-1"
        />
        <Section
          title="Agent"
          description={`How ${product.agent_name} sounds and what it won’t do.`}
          className="lg:col-start-2 lg:row-span-2 lg:row-start-1"
        >
          <Surface>
            <ProductForm
              apiUrl={apiUrl}
              productId={product.id}
              initial={product}
              submitLabel="Save changes"
              formLabel="Agent settings"
              onSaved={setProduct}
            />
          </Surface>
        </Section>
        <ProductSessions
          apiUrl={apiUrl}
          productId={product.id}
          agentName={product.agent_name}
          className="lg:col-start-1"
        />
      </div>
    </main>
  );
}
