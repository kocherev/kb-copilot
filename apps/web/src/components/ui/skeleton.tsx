import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

// Decorative. Wrap skeletons in <Loading> so screen readers hear one status.
export function Skeleton({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      aria-hidden
      data-slot="skeleton"
      className={cn(
        "relative overflow-hidden rounded-md bg-surface-sunken before:absolute before:inset-0 before:-translate-x-full before:bg-linear-to-r before:from-transparent before:via-foreground/6 before:to-transparent motion-safe:before:animate-shimmer",
        className,
      )}
      {...props}
    />
  );
}

export function Loading({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div role="status" aria-busy className={className}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}
