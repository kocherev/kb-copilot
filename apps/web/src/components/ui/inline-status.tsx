import { CircleCheck, Info, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const tones = {
  neutral: { Icon: Info, className: "text-muted-foreground" },
  success: { Icon: CircleCheck, className: "text-success" },
  warning: { Icon: TriangleAlert, className: "text-warning" },
} as const;

// Render it before there is anything to say, with null children, so screen
// readers already know the region when the text arrives.
export function InlineStatus({
  tone = "neutral",
  className,
  children,
}: {
  tone?: keyof typeof tones;
  className?: string;
  children: ReactNode;
}) {
  const { Icon, className: toneClass } = tones[tone];
  return (
    <p role="status" className={cn("flex min-w-0 items-start gap-2 text-sm", toneClass, className)}>
      {children ? (
        <>
          <Icon aria-hidden className="mt-0.5 size-4 shrink-0" />
          <span className="min-w-0 text-pretty [overflow-wrap:anywhere]">{children}</span>
        </>
      ) : null}
    </p>
  );
}
