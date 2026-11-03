import { expect, test } from "vitest";

import spec from "../../openapi.json";
import { errorDetail } from "@/lib/api/client";
import { fileSize, indexedLabel, productLoad, voices } from "@/lib/product";

const product = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Acme",
  description: "Acme helps customers reset passwords.",
  tone: "calm and brief",
  refusal_rules: "Do not invent a refund policy.",
  agent_name: "Shawn",
  voice: "Sulafat" as const,
};

test("indexed label matches the chunk count", () => {
  expect(indexedLabel(1)).toBe("1 section");
  expect(indexedLabel(2)).toBe("2 sections");
});

test("file size reads in KB under a megabyte and never rounds to zero", () => {
  expect(fileSize(10)).toBe("1 KB");
  expect(fileSize(5_000)).toBe("5 KB");
  expect(fileSize(2_200_000)).toBe("2.1 MB");
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

test("the voice list is the one the API accepts, default first", () => {
  const accepted = spec.components.schemas.ProductWrite.properties.voice.enum;

  expect(voices.map((voice) => voice.value)).toEqual(accepted);
  expect(spec.components.schemas.ProductWrite.properties.voice.default).toBe(
    voices[0]?.value,
  );
});
