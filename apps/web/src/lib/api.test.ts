import { afterEach, expect, test, vi } from "vitest";

import { loadProduct } from "@/lib/api";

const product = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Acme",
  description: "Acme helps customers reset passwords.",
  tone: "calm and brief",
  refusal_rules: "Do not invent a refund policy.",
};

function stubProductApi(origin: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) !== `${origin}/products/${product.id}`) {
        throw new TypeError("fetch failed");
      }
      return { ok: true, status: 200, json: async () => product };
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

test("server pages load the product over the internal API URL", async () => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  vi.stubEnv("API_INTERNAL_URL", "http://api:8000");
  stubProductApi("http://api:8000");

  expect(await loadProduct(product.id)).toEqual({ status: "ready", product });
});

test("without an internal URL the public API URL is used", async () => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  vi.stubEnv("API_INTERNAL_URL", undefined);
  stubProductApi("http://localhost:8000");

  expect(await loadProduct(product.id)).toEqual({ status: "ready", product });
});

test("an unreachable API reads as a load error", async () => {
  vi.stubEnv("API_INTERNAL_URL", "http://api:8000");
  stubProductApi("http://elsewhere:8000");

  expect(await loadProduct(product.id)).toEqual({
    status: "error",
    message: "Could not load the product.",
  });
});
