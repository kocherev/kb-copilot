import { Compass } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-[640px] min-w-0 flex-col justify-center px-4 py-10 sm:px-8">
      <h1 className="sr-only">Page not found</h1>
      <EmptyState
        icon={Compass}
        title="This page doesn’t exist"
        description="The link may be old, or the page may have moved."
        action={<Button render={<Link href="/" />}>Go to your products</Button>}
      />
    </main>
  );
}
