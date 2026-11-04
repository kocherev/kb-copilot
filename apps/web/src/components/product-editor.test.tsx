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
  agent_name: "Shawn",
  voice: "Sulafat" as const,
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
  expect(screen.getByRole("link", { name: "All products" }).getAttribute("href")).toBe("/");
  expect(screen.getByRole("link", { name: "Start session" }).getAttribute("href")).toBe(
    `/products/${product.id}/session`,
  );
  expect(screen.getByRole("region", { name: "Knowledge" })).toBeDefined();
  expect(screen.getByRole("region", { name: "Agent" })).toBeDefined();
  expect(screen.getByRole("region", { name: "Sessions" })).toBeDefined();
  expect(await screen.findByText("No documents yet")).toBeDefined();

  fireEvent.change(screen.getByLabelText("Name"), {
    target: { value: "Acme Care" },
  });
  fireEvent.change(screen.getByLabelText("Agent name"), { target: { value: "Mina" } });
  fireEvent.change(screen.getByLabelText("Voice"), { target: { value: "Puck" } });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

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
    agent_name: "Mina",
    voice: "Puck",
  });
  expect(calls.map((call) => call.url)).toContain(
    `http://localhost:8000/products/${product.id}/documents`,
  );
});

test("missing product says it was not found and links back", async () => {
  const loaded: ProductLoad = { status: "missing" };
  render(<ProductEditor apiUrl="http://localhost:8000" loaded={loaded} />);

  expect(await screen.findByText("Product not found")).toBeDefined();
  expect(screen.getByRole("link", { name: "All products" }).getAttribute("href")).toBe("/");
  expect(screen.queryByLabelText("Name")).toBeNull();
});

test("a product that failed to load says why and offers to try again", () => {
  render(
    <ProductEditor
      apiUrl="http://localhost:8000"
      loaded={{ status: "error", message: "Could not load the product." }}
    />,
  );

  expect(screen.getByRole("alert").textContent).toContain("Could not load the product.");
  expect(screen.getByRole("button", { name: "Try again" })).toBeDefined();
  expect(screen.queryByLabelText("Name")).toBeNull();
});

test("field hints name the agent, or say the agent when the name is empty", async () => {
  stubApi(() => ({ status: 200, body: [] }));
  render(<ProductEditor apiUrl="http://localhost:8000" loaded={{ status: "ready", product }} />);
  // Let the documents and sessions loads land before the test ends.
  await screen.findByText("No documents yet");
  await screen.findByText("No sessions yet");

  expect(screen.getByText("How Shawn should sound, such as “calm and brief”.")).toBeDefined();
  expect(screen.getByText("What Shawn must not do.")).toBeDefined();

  fireEvent.change(screen.getByLabelText("Agent name"), { target: { value: " " } });
  expect(screen.getByText("How the agent should sound, such as “calm and brief”.")).toBeDefined();
  expect(screen.getByText("What the agent must not do.")).toBeDefined();
});
