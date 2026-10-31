import { Button } from "@/components/ui/button";

export function healthUrl(apiUrl: string): string {
  return `${apiUrl.replace(/\/+$/, "")}/health`;
}

export function HomePage({ apiUrl }: { apiUrl: string }) {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-lg flex-col justify-center gap-8 px-6 py-16">
      <div className="flex flex-col gap-3">
        <h1 className="text-2xl font-medium tracking-tight text-foreground">
          Knowledge base copilot
        </h1>
        <p className="text-sm leading-6 text-muted-foreground">
          Upload a knowledge base, index it, and talk with a support agent
          while it sees your screen.
        </p>
        <p className="text-sm leading-6 text-muted-foreground">
          Indexing and live sessions are not built yet. This page only shows
          that the web app started.
        </p>
      </div>
      <Button render={<a href={healthUrl(apiUrl)} />}>API health</Button>
    </main>
  );
}
