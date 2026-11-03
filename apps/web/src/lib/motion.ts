import type { CSSProperties } from "react";

// Past this many items the rest arrive together, so a long list never waits.
const MAX_STEPS = 8;

// For a list's first appearance with `animate-enter`. Reduced
// motion sets the step to zero.
export function stagger(index: number): CSSProperties {
  return { animationDelay: `calc(var(--stagger-step) * ${Math.min(index, MAX_STEPS)})` };
}
