import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

// Adapted from https://ds.asanshay.com/r/page-header.json: a serif title, an
// optional way back, and the page's actions on the trailing edge.
export function PageHeader({
  title,
  description,
  back,
  actions,
}: {
  title: string;
  description?: ReactNode;
  back?: { href: string; label: string };
  actions?: ReactNode;
}) {
  return (
    <header className="flex min-w-0 flex-col gap-4">
      {back ? (
        <Link
          href={back.href}
          className="-ml-1 flex w-fit items-center gap-1 rounded-control px-1 py-0.5 text-meta text-muted-foreground transition-colors duration-150 ease-out outline-none hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
        >
          <ArrowLeft aria-hidden className="size-3.5" />
          {back.label}
        </Link>
      ) : null}
      <div className="flex min-w-0 flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="flex min-w-0 flex-col gap-2">
          <h1 className="font-display text-title text-balance text-foreground [overflow-wrap:anywhere] sm:text-display">
            {title}
          </h1>
          {description ? (
            <p className="max-w-[65ch] text-body text-pretty text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
    </header>
  );
}
