import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col items-center gap-3 rounded-card border border-dashed border-border-strong px-6 py-10 text-center animate-enter",
        className,
      )}
    >
      {Icon ? (
        <span className="grid size-10 place-items-center rounded-full bg-primary-soft text-primary-soft-foreground">
          <Icon aria-hidden className="size-5" />
        </span>
      ) : null}
      <p className="font-display text-xl/tight text-balance text-foreground">{title}</p>
      {description ? (
        <p className="max-w-[44ch] text-body text-pretty text-muted-foreground">{description}</p>
      ) : null}
      {action ? <div className="mt-1 flex flex-wrap justify-center gap-2">{action}</div> : null}
    </div>
  );
}
