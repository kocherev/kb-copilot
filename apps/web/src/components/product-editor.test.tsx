import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ProductEditor } from "@/components/product-editor";
import type { ProductLoad } from "@/lib/product";
import { TEST_JWT, stubApi } from "@/test/api-stub";

const product = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "X".repeat(80),
  description: "Acme helps customers reset passwords.",
  tone: "calm and brief",
  refusal_rules: "Do not invent a refund policy.",
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("saves config and shows the product's documents", async () => {
  const calls = stubApi((call) =>
    call.method === "PUT"
      ? { status: 200, body: { ...product, ...(call.json as object) } }
      : { status: 200, body: [] },
  );
  render(
    <ProductEditor
      apiUrl="http://localhost:8000"
      loaded={{ status: "ready", product }}
    />,
  );

  const heading = await screen.findByRole("heading", { level: 1 });
  expect(heading.textContent).toBe(product.name);
  expect(heading.className).toMatch(/anywhere/);
  expect(screen.getByRole("link", { name: "New product" }).getAttribute("href")).toBe(
    "/",
  );
  expect(screen.getByRole("link", { name: "Start session" }).getAttribute("href")).toBe(
    `/products/${product.id}/session`,
  );
  expect(await screen.findByText("No documents yet.")).toBeDefined();

  fireEvent.change(screen.getByLabelText("Name"), {
    target: { value: "Acme Care" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Acme Care" }),
  ).toBeDefined();
  expect(screen.getByText("Saved")).toBeDefined();
  const put = calls.find((call) => call.method === "PUT");
  expect(put?.url).toBe(`http://localhost:8000/products/${product.id}`);
  expect(put?.authorization).toBe(`Bearer ${TEST_JWT}`);
  expect(put?.json).toMatchObject({
    name: "Acme Care",
    description: product.description,
    tone: product.tone,
    refusal_rules: product.refusal_rules,
  });
  const listed = calls.find((call) => call.method === "GET");
  expect(listed?.url).toBe(`http://localhost:8000/products/${product.id}/documents`);
});

test("missing product says it was not found", async () => {
  const loaded: ProductLoad = { status: "missing" };
  render(<ProductEditor apiUrl="http://localhost:8000" loaded={loaded} />);

  expect(await screen.findByText("Product not found.")).toBeDefined();
  expect(screen.getByText("Product not found.").className).toMatch(/leading-6/);
  expect(screen.getByRole("link", { name: "New product" }).getAttribute("href")).toBe(
    "/",
  );
  expect(screen.queryByLabelText("Name")).toBeNull();
});
