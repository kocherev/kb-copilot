import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { SignOutButton } from "@/components/sign-out-button";
import { Skeleton } from "@/components/ui/skeleton";
import { auth } from "@/lib/auth";

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <AppShell
      account={
        <Suspense fallback={<Skeleton className="h-8 w-24 rounded-full" />}>
          <Account />
        </Suspense>
      }
    >
      {children}
    </AppShell>
  );
}

async function Account() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) {
    redirect("/sign-in");
  }
  return (
    <div className="flex min-w-0 items-center gap-2">
      <p
        title={session.user.email}
        className="min-w-0 truncate text-meta text-muted-foreground max-md:sr-only md:max-w-48"
      >
        {session.user.email}
      </p>
      <SignOutButton />
    </div>
  );
}
