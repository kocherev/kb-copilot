import * as React from "react";

import { cn } from "@/lib/utils";

import { fieldClass } from "./input";

// A native select, skinned like Input. The ds.asanshay.com select needs Radix
// and an icon package for what one browser control already does.
function Select({ className, ...props }: React.ComponentProps<"select">) {
  return (
    <select
      data-slot="select"
      className={cn(fieldClass, "flex h-10 px-3", className)}
      {...props}
    />
  );
}

export { Select };
