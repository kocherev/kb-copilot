import { expect, test } from "vitest";

import { requireAuthSecret } from "@/lib/auth-secret";

test("a missing, placeholder, or short secret stops startup", () => {
  expect(() => requireAuthSecret(undefined)).toThrow("BETTER_AUTH_SECRET");
  expect(() => requireAuthSecret("replace-me")).toThrow("BETTER_AUTH_SECRET");
  expect(() => requireAuthSecret("a".repeat(31))).toThrow("BETTER_AUTH_SECRET");
  expect(requireAuthSecret(` ${"a".repeat(32)} `)).toBe("a".repeat(32));
});
