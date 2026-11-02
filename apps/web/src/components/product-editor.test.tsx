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

test("saves config and uploads documents for that product", async () => {
  const calls = stubApi((call) =>
    call.method === "PUT"
      ? { status: 200, body: { ...product, ...(call.json as object) } }
      : {
          status: 201,
          body: { status: "indexed", chunk_count: 2, error: null, product_id: product.id },
        },
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

  fireEvent.change(screen.getByLabelText("Name"), {
    target: { value: "Acme Care" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Acme Care" }),
  ).toBeDefined();
  expect(screen.getByText("Saved")).toBeDefined();
  const [put] = calls;
  expect(put?.url).toBe(`http://localhost:8000/products/${product.id}`);
  expect(put?.authorization).toBe(`Bearer ${TEST_JWT}`);
  expect(put?.json).toMatchObject({
    name: "Acme Care",
    description: product.description,
    tone: product.tone,
    refusal_rules: product.refusal_rules,
  });

  const upload = screen.getByRole("button", { name: "Upload documents" });
  expect(upload.hasAttribute("disabled")).toBe(true);
  const file = new File(
    ["# Notes\n\nPassword reset links expire after 30 minutes.\n"],
    "notes.md",
    { type: "text/markdown" },
  );
  fireEvent.change(screen.getByLabelText("Files"), {
    target: { files: [file] },
  });
  expect(upload.hasAttribute("disabled")).toBe(false);
  fireEvent.click(upload);

  expect(await screen.findByText("Indexed 2 chunks.")).toBeDefined();
  const posted = calls[1];
  expect(posted?.method).toBe("POST");
  expect(posted?.url).toBe(`http://localhost:8000/products/${product.id}/documents`);
  expect(posted?.authorization).toBe(`Bearer ${TEST_JWT}`);
  expect(posted?.form?.getAll("files")).toHaveLength(1);
  expect((posted?.form?.get("files") as File).name).toBe("notes.md");
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

test("a failed upload shows the job error", async () => {
  stubApi(() => ({
    status: 201,
    body: { status: "failed", chunk_count: 0, error: "broken.pdf has no text" },
  }));
  render(
    <ProductEditor
      apiUrl="http://localhost:8000"
      loaded={{ status: "ready", product }}
    />,
  );
  await screen.findByLabelText("Name");
  const file = new File(["%PDF"], "broken.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("Files"), { target: { files: [file] } });
  fireEvent.click(screen.getByRole("button", { name: "Upload documents" }));

  expect(await screen.findByRole("alert")).toBeDefined();
  expect(screen.getByRole("alert").textContent).toBe("broken.pdf has no text");
});
