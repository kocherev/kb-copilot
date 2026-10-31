import { ProductForm } from "@/components/product-form";
import { Button } from "@/components/ui/button";
import { apiPath } from "@/lib/api";

export function HomePage({ apiUrl }: { apiUrl: string }) {
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
      <ProductForm
        apiUrl={apiUrl}
        submitLabel="Create product"
        formLabel="Create product"
      />
      <Button variant="outline" render={<a href={apiPath(apiUrl, "/health")} />}>
        API health
      </Button>
    </main>
  );
}
