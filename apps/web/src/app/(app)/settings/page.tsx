import { headers } from "next/headers";
import { Suspense } from "react";

import { LinearConnection, LinearSkeleton } from "@/components/linear-connection";
import { PageHeader } from "@/components/ui/page-header";
import { Section } from "@/components/ui/section";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { Surface } from "@/components/ui/surface";
import { publicApiUrl } from "@/lib/api/client";
import { auth } from "@/lib/auth";
import { linearNotice } from "@/lib/linear";

export default function Page({ searchParams }: PageProps<"/settings">) {
  return (
    <main className="mx-auto flex w-full max-w-[640px] min-w-0 flex-col gap-10 px-4 py-10 sm:gap-12 sm:px-8 sm:py-14">
      <PageHeader title="Settings" description="Your account and the tools the agent can use." />
      <Section title="Account">
        <Suspense fallback={<AccountSkeleton />}>
          <Account />
        </Suspense>
      </Section>
      <Section
        title="Linear"
        description="When the agent can’t solve a problem, it can propose a Linear ticket. You approve each one on the session page before it’s created."
      >
        <Suspense fallback={<LinearSkeleton />}>
          <LinearRoute searchParams={searchParams} />
        </Suspense>
      </Section>
    </main>
  );
}

async function LinearRoute({ searchParams }: Pick<PageProps<"/settings">, "searchParams">) {
  const { linear } = await searchParams;
  return <LinearConnection apiUrl={publicApiUrl()} notice={linearNotice(linear)} />;
}

async function Account() {
  const session = await auth.api.getSession({ headers: await headers() });
  // The app layout already sends a signed-out visitor to sign in.
  if (!session) {
    return null;
  }
  return (
    <Surface>
      <dl className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-3 text-sm">
        <dt className="text-muted-foreground">Name</dt>
        <dd className="text-foreground [overflow-wrap:anywhere]">{session.user.name}</dd>
        <dt className="text-muted-foreground">Email</dt>
        <dd className="text-foreground [overflow-wrap:anywhere]">{session.user.email}</dd>
      </dl>
    </Surface>
  );
}

function AccountSkeleton() {
  return (
    <Surface>
      <Loading label="Loading your account" className="flex min-w-0 flex-col gap-3">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-4 w-56" />
      </Loading>
    </Surface>
  );
}
