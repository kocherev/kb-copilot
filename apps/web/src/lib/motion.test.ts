import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "vitest";

import { stagger } from "@/lib/motion";

const tokens = readFileSync(join(__dirname, "../styles/tokens.css"), "utf8");

function reducedMotionBlock(css: string): string {
  const start = css.indexOf("@media (prefers-reduced-motion: reduce)");
  expect(start).toBeGreaterThan(-1);
  return css.slice(start, css.indexOf("\n}\n", start));
}

test("reduced motion turns every enter and exit into a plain fade", () => {
  const block = reducedMotionBlock(tokens);
  expect(block).toMatch(/--motion-y:\s*0px/);
  expect(block).toMatch(/--motion-exit-y:\s*0px/);
  expect(block).toMatch(/--motion-scale:\s*1/);
  expect(block).toMatch(/--stagger-step:\s*0ms/);
});

test("stagger delays each item by one step and stops growing after eight", () => {
  expect(stagger(0).animationDelay).toBe("calc(var(--stagger-step) * 0)");
  expect(stagger(3).animationDelay).toBe("calc(var(--stagger-step) * 3)");
  expect(stagger(40).animationDelay).toBe("calc(var(--stagger-step) * 8)");
});

test("the enter animation keeps no last frame, so fixed children stay fixed", () => {
  const globals = readFileSync(join(__dirname, "../app/globals.css"), "utf8");
  expect(globals).toMatch(/--animate-enter: enter [^;]* backwards;/);
});
