import { expect, test } from "vitest";

import { errorDetail } from "@/lib/api/client";
import { indexedLabel, productLoad } from "@/lib/product";

const product = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Acme",
  description: "Acme helps customers reset passwords.",
  tone: "calm and brief",
  refusal_rules: "Do not invent a refund policy.",
};

test("indexed label matches the chunk count", () => {
  expect(indexedLabel(1)).toBe("Indexed 1 chunk.");
  expect(indexedLabel(2)).toBe("Indexed 2 chunks.");
});

test("product load maps not found, errors, and a saved product", () => {
  expect(productLoad(404, undefined, { detail: "product not found" })).toEqual({
    status: "missing",
  });
  expect(productLoad(401, undefined, { detail: "invalid token" })).toEqual({
    status: "error",
    message: "invalid token",
  });
  expect(productLoad(500, undefined, null)).toEqual({
    status: "error",
    message: "Could not load the product.",
  });
  expect(productLoad(200, product, undefined)).toEqual({ status: "ready", product });
});

test("a validation error names the field", () => {
  expect(
    errorDetail(
      { detail: [{ loc: ["body", "refusal_rules"], msg: "String should have at least 1 character" }] },
      "fallback",
    ),
  ).toBe("refusal rules: String should have at least 1 character");
  expect(errorDetail({ detail: [] }, "fallback")).toBe("fallback");
});
