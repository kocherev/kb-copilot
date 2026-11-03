"use client";

import { LayoutGrid, Settings, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { ThemeToggle } from "@/components/ui/theme-toggle";

const focusRing =
  "outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring";

const nav: { href: string; label: string; Icon: LucideIcon; matches: (path: string) => boolean }[] = [
  {
    href: "/",
    label: "Products",
    Icon: LayoutGrid,
    matches: (path) => path === "/" || path.startsWith("/products"),
  },
  {
    href: "/settings",
    label: "Settings",
    Icon: Settings,
    matches: (path) => path.startsWith("/settings"),
  },
];

function Mark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="size-6 text-primary">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.75" opacity="0.45" />
      <circle cx="12" cy="12" r="4" fill="currentColor" />
    </svg>
  );
}

export function AppShell({ account, children }: { account: ReactNode; children: ReactNode }) {
  const pathname = usePathname();
  return (
    <>
      <a
        href="#content"
        className={`sr-only z-(--z-overlay) rounded-control bg-surface px-3 py-2 text-sm shadow-float focus:not-sr-only focus:fixed focus:top-2 focus:left-2 ${focusRing}`}
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-(--z-sticky) border-b border-border bg-background/85 backdrop-blur-md">
        <div className="mx-auto flex h-14 w-full max-w-[1080px] min-w-0 items-center gap-1 px-4 sm:gap-2 sm:px-8">
          <Link
            href="/"
            className={`mr-1 flex shrink-0 items-center gap-2 rounded-control py-1 pr-1 text-sm font-semibold text-foreground sm:mr-3 ${focusRing}`}
          >
            <Mark />
            <span className="max-sm:sr-only">KB Copilot</span>
          </Link>
          <nav aria-label="Main" className="flex min-w-0 items-center gap-1">
            {nav.map(({ href, label, Icon, matches }) => (
              <Link
                key={href}
                href={href}
                aria-current={matches(pathname) ? "page" : undefined}
                className={`flex h-8 items-center gap-1.5 rounded-full px-2.5 text-sm font-medium text-muted-foreground transition-[color,background-color] duration-150 ease-out hover:bg-surface-hover hover:text-foreground aria-[current=page]:bg-surface-sunken aria-[current=page]:text-foreground pointer-coarse:h-10 ${focusRing}`}
              >
                <Icon aria-hidden className="size-4" />
                <span className="max-sm:sr-only">{label}</span>
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex min-w-0 items-center gap-2">
            <ThemeToggle />
            {account}
          </div>
        </div>
      </header>
      <div id="content" tabIndex={-1} className="outline-none">
        {children}
      </div>
    </>
  );
}
