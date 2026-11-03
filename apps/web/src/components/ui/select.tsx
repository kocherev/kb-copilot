import * as React from "react";

import { cn } from "@/lib/utils";

// A native select, skinned like Input. The ds.asanshay.com select needs Radix
// and an icon package for what one browser control already does.
function Select({ className, ...props }: React.ComponentProps<"select">) {
  return (
    <select
      data-slot="select"
      className={cn(
        "border-input dark:bg-input/30 flex h-10 w-full min-w-0 rounded-xl border bg-transparent px-3 py-2 text-sm shadow-md shadow-shade outline-none disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:border-primary focus-visible:ring-[3px] focus-visible:ring-primary/30",
        "hover:border-border/0 hover:bg-muted hover:shadow-none",
        "motion-safe:transition-[color,box-shadow,background-color,border-color] motion-safe:duration-150 motion-safe:ease-out motion-safe:hover:duration-75",
        className,
      )}
      {...props}
    />
  );
}

export { Select };
