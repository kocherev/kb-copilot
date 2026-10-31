import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ProductEditor } from "@/components/product-editor";
import type { ProductLoad } from "@/lib/product";

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

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

test("saves config and uploads documents for that product", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === "PUT") {
      expect(url).toBe(`http://localhost:8000/products/${product.id}`);
      return jsonResponse({ ...product, ...JSON.parse(String(init.body)) });
    }
    expect(url).toBe(`http://localhost:8000/products/${product.id}/documents`);
    const form = init?.body as FormData;
    expect(form.getAll("files")).toHaveLength(1);
    expect((form.get("files") as File).name).toBe("notes.md");
    return jsonResponse({
      status: "indexed",
      chunk_count: 2,
      error: null,
      product_id: product.id,
    });
  });
  vi.stubGlobal("fetch", fetchMock);
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

  fireEvent.change(screen.getByLabelText("Name"), {
    target: { value: "Acme Care" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Acme Care" }),
  ).toBeDefined();
  expect(screen.getByText("Saved")).toBeDefined();
  const put = fetchMock.mock.calls.find((call) => call[1]?.method === "PUT");
  expect(String(put?.[0])).toBe(`http://localhost:8000/products/${product.id}`);
  expect(JSON.parse(String(put?.[1]?.body))).toMatchObject({
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
  const posted = fetchMock.mock.calls.find((call) =>
    String(call[0]).endsWith("/documents"),
  );
  expect(posted?.[1]?.method).toBe("POST");
});

test("missing product says it was not found", async () => {
  const loaded: ProductLoad = { status: "missing" };
  render(<ProductEditor apiUrl="http://localhost:8000" loaded={loaded} />);

  expect(await screen.findByText("Product not found.")).toBeDefined();
  expect(screen.queryByLabelText("Name")).toBeNull();
});

test("a failed upload shows the job error", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe("POST");
      expect(String(input)).toContain("/documents");
      return jsonResponse({
        status: "failed",
        chunk_count: 0,
        error: "broken.pdf has no text",
      });
    }),
  );
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
