import * as React from "react";

import { cn } from "@/lib/utils";

// Shared by Input, Textarea and Select so every field looks and reacts the same.
export const fieldClass = cn(
  "w-full min-w-0 rounded-control border border-input bg-surface text-base text-foreground outline-none sm:text-sm",
  "placeholder:text-muted-foreground",
  "hover:border-input-hover",
  "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/15",
  "aria-invalid:border-destructive aria-invalid:focus-visible:ring-destructive/15",
  "disabled:cursor-not-allowed disabled:opacity-50",
  "motion-safe:transition-[border-color,box-shadow] motion-safe:duration-150 motion-safe:ease-out",
);

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        fieldClass,
        "flex h-10 px-3 file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
