"use client";

import { LayoutGrid, Settings, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, type ReactNode } from "react";

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


function NavLinks({ pathname }: { pathname: string | null }) {
  return nav.map(({ href, label, Icon, matches }) => (
    <Link
      key={href}
      href={href}
      aria-current={pathname !== null && matches(pathname) ? "page" : undefined}
      className={`flex h-8 items-center gap-1.5 rounded-full px-2.5 text-sm font-medium text-muted-foreground transition-[color,background-color,box-shadow] duration-150 ease-out hover:bg-surface-hover hover:text-foreground aria-[current=page]:bg-surface aria-[current=page]:text-foreground aria-[current=page]:shadow-soft pointer-coarse:h-10 ${focusRing}`}
    >
      <Icon aria-hidden className="size-4" />
      <span className="max-sm:sr-only">{label}</span>
    </Link>
  ));
}

function CurrentNavLinks() {
  return <NavLinks pathname={usePathname()} />;
}

export function AppShell({ account, children }: { account: ReactNode; children: ReactNode }) {
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
          <nav aria-label="Main" className="flex min-w-0 items-center gap-1">
            {/* The pathname of a page with an unknown [id] exists only at
                request time, so the prerendered shell shows the links unmarked. */}
            <Suspense fallback={<NavLinks pathname={null} />}>
              <CurrentNavLinks />
            </Suspense>
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
