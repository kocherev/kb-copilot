import { headers } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Suspense } from "react";

import { SignOutButton } from "@/components/sign-out-button";
import { auth } from "@/lib/auth";

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <>
      <Suspense fallback={null}>
        <AccountBar />
      </Suspense>
      {children}
    </>
  );
}

async function AccountBar() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) {
    redirect("/sign-in");
  }
  return (
    <header className="mx-auto flex w-full max-w-3xl min-w-0 items-center justify-end gap-3 px-6 pt-6">
      <p className="min-w-0 truncate text-sm text-muted-foreground">{session.user.email}</p>
      <Link
        href="/settings"
        className="text-sm underline underline-offset-4 focus-visible:[outline:var(--hui-focus-ring)] focus-visible:outline-offset-[var(--hui-focus-ring-offset-accent)]"
      >
        Settings
      </Link>
      <SignOutButton />
    </header>
  );
}
