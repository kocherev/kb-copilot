import { CircleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Say what failed and what to do next. Pass onRetry when trying again can help.
export function InlineError({
  children,
  onRetry,
  className,
}: {
  children: ReactNode;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2 rounded-control bg-destructive-soft px-3.5 py-2.5 text-sm text-destructive",
        className,
      )}
    >
      <CircleAlert aria-hidden className="size-4 shrink-0" />
      <p className="min-w-0 flex-1 text-pretty [overflow-wrap:anywhere]">{children}</p>
      {onRetry ? (
        <Button variant="outline" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}
