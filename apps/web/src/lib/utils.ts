import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// The font sizes from globals.css. Unlisted, tailwind-merge reads text-meta as
// a colour and drops it next to text-muted-foreground.
const twMerge = extendTailwindMerge({
  extend: { theme: { text: ["display", "title", "heading", "body", "meta", "overline"] } },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
