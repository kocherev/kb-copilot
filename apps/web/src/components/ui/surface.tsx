import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

// Adapted from https://ds.asanshay.com/r/card.json, cut to the two surfaces
// the app uses. A raised surface may hold sunken wells, never another raised
// one. The transparent border draws the edge in forced-colors mode.
const surfaceVariants = cva("min-w-0 rounded-card border border-transparent", {
  variants: {
    variant: {
      raised: "bg-surface shadow-soft",
      sunken: "bg-surface-sunken",
    },
    padding: {
      none: "",
      default: "p-4 sm:p-5",
    },
  },
  defaultVariants: { variant: "raised", padding: "default" },
});

export function Surface({
  className,
  variant,
  padding,
  ...props
}: ComponentProps<"div"> & VariantProps<typeof surfaceVariants>) {
  return (
    <div data-slot="surface" className={cn(surfaceVariants({ variant, padding }), className)} {...props} />
  );
}
