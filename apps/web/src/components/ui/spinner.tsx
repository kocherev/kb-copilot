import { LoaderCircle } from "lucide-react";

import { cn } from "@/lib/utils";

// Decorative inside a button whose label already says what is happening.
// Give it a label when it stands alone. Under reduced motion it stops
// spinning and the glyph and label carry the state.
export function Spinner({ label, className }: { label?: string; className?: string }) {
  const icon = (
    <LoaderCircle aria-hidden className={cn("size-4 shrink-0 motion-safe:animate-spin", className)} />
  );
  if (!label) {
    return icon;
  }
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-muted-foreground">
      {icon}
      {label}
    </span>
  );
}
