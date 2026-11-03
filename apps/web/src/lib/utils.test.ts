import { expect, test } from "vitest";

import { cn } from "@/lib/utils";

test("a custom font size and a text colour both survive", () => {
  expect(cn("text-meta", "text-muted-foreground")).toBe("text-meta text-muted-foreground");
  expect(cn("text-title text-foreground")).toBe("text-title text-foreground");
});

test("a later custom font size replaces an earlier one", () => {
  expect(cn("text-body", "text-meta")).toBe("text-meta");
  expect(cn("text-sm", "text-body")).toBe("text-body");
});
