import * as React from "react";

import { cn } from "@/lib/utils";

// Source: https://ds.asanshay.com/r/input.json
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "border-input file:text-foreground placeholder:text-muted-foreground selection:bg-primary selection:text-primary-foreground dark:bg-input/30 flex h-10 w-full min-w-0 rounded-xl border bg-transparent px-4 py-2 text-sm shadow-md shadow-shade outline-none file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:border-primary focus-visible:ring-[3px] focus-visible:ring-primary/30",
        "aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40",
        "hover:border-border/0 hover:bg-muted hover:shadow-none",
        "motion-safe:transition-[color,box-shadow,background-color,border-color] motion-safe:duration-150 motion-safe:ease-out motion-safe:hover:duration-75",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
