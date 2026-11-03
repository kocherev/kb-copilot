import Link from "next/link";
import { Suspense } from "react";

import { LinearConnection } from "@/components/linear-connection";
import { publicApiUrl } from "@/lib/api/client";
import { linearNotice } from "@/lib/linear";

export default function Page({ searchParams }: PageProps<"/settings">) {
  return (
    <Suspense
      fallback={
        <main className="mx-auto flex min-h-dvh w-full max-w-lg flex-col px-6 py-16 text-sm leading-6 text-muted-foreground">
          Loading settings.
        </main>
      }
    >
      <SettingsRoute searchParams={searchParams} />
    </Suspense>
  );
}

async function SettingsRoute({
  searchParams,
}: Pick<PageProps<"/settings">, "searchParams">) {
  const { linear } = await searchParams;
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-lg min-w-0 flex-col gap-8 px-6 py-16">
      <Link
        className="text-sm underline underline-offset-4 focus-visible:[outline:var(--hui-focus-ring)] focus-visible:outline-offset-[var(--hui-focus-ring-offset-accent)]"
        href="/"
      >
        Products
      </Link>
      <h1 className="text-balance text-2xl font-medium tracking-tight text-foreground">
        Settings
      </h1>
      <LinearConnection apiUrl={publicApiUrl()} notice={linearNotice(linear)} />
    </main>
  );
}
