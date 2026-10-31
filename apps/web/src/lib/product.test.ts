import { expect, test } from "vitest";

import { indexedLabel, productFromResponse } from "@/lib/product";

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

test("product response maps not found, errors, and a saved product", () => {
  expect(productFromResponse(404, { detail: "product not found" })).toEqual({
    status: "missing",
  });
  expect(
    productFromResponse(400, { detail: "name must be 1 to 120 characters" }),
  ).toEqual({
    status: "error",
    message: "name must be 1 to 120 characters",
  });
  expect(productFromResponse(422, { detail: [{ loc: ["path", "id"] }] })).toEqual({
    status: "error",
    message: "Could not load the product.",
  });
  expect(productFromResponse(200, product)).toEqual({
    status: "ready",
    product,
  });
});
