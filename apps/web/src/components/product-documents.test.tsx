import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ProductDocuments } from "@/components/product-documents";
import { TEST_JWT, stubApi, type ApiCall } from "@/test/api-stub";

const PRODUCT = "11111111-1111-4111-8111-111111111111";
const LIST = `http://localhost:8000/products/${PRODUCT}/documents`;

function document(title: string, status: string, extra: object = {}) {
  return {
    id: `id-${title}`,
    source: `upload://${title}`,
    title,
    status,
    chunk_count: status === "indexed" ? 2 : 0,
    error: null,
    job_id: "job-1",
    ...extra,
  };
}

function renderDocuments() {
  render(<ProductDocuments apiUrl="http://localhost:8000" productId={PRODUCT} />);
}

function listCalls(calls: ApiCall[]) {
  return calls.filter((call) => call.method === "GET" && call.url === LIST);
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("lists each document with its status and error", async () => {
  stubApi(() => ({
    status: 200,
    body: [
      document("broken.pdf", "failed", { error: "could not read this file" }),
      document("notes.md", "indexed"),
    ],
  }));
  renderDocuments();

  const list = await screen.findByRole("list", { name: "Documents" });
  const [broken, notes] = Array.from(list.querySelectorAll("li"));
  expect(broken?.textContent).toContain("broken.pdf");
  expect(broken?.textContent).toContain("Failed: could not read this file.");
  expect(notes?.textContent).toContain("Indexed 2 chunks.");
  expect(screen.getByRole("status").textContent).toBe("1 indexed, 0 in progress, 1 failed.");
});

test("says so when there are no documents", async () => {
  stubApi(() => ({ status: 200, body: [] }));
  renderDocuments();

  expect(await screen.findByText("No documents yet.")).toBeDefined();
});

test("an API failure shows an error instead of an empty list", async () => {
  stubApi(() => ({ status: 500, body: { detail: "boom" } }));
  renderDocuments();

  expect((await screen.findByRole("alert")).textContent).toBe("Could not load documents.");
  expect(screen.queryByText("No documents yet.")).toBeNull();
});

test("uploads files, then polls until they settle and stops", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  let reads = 0;
  const calls = stubApi((call) => {
    if (call.method === "POST") {
      return { status: 202, body: { id: "job-1", status: "queued" } };
    }
    reads += 1;
    if (reads === 1) {
      return { status: 200, body: [] };
    }
    return {
      status: 200,
      body: [document("notes.md", reads < 4 ? "indexing" : "indexed")],
    };
  });
  renderDocuments();
  await screen.findByText("No documents yet.");

  const upload = screen.getByRole("button", { name: "Upload documents" });
  expect(upload.hasAttribute("disabled")).toBe(true);
  const file = new File(["# Notes"], "notes.md", { type: "text/markdown" });
  fireEvent.change(screen.getByLabelText("Files"), { target: { files: [file] } });
  expect(upload.hasAttribute("disabled")).toBe(false);
  fireEvent.click(upload);

  expect(await screen.findByText("Indexing.")).toBeDefined();
  const posted = calls.find((call) => call.method === "POST");
  expect(posted?.url).toBe(LIST);
  expect(posted?.authorization).toBe(`Bearer ${TEST_JWT}`);
  expect((posted?.form?.get("files") as File).name).toBe("notes.md");

  await act(() => vi.advanceTimersByTimeAsync(2000));
  await act(() => vi.advanceTimersByTimeAsync(2000));
  expect(await screen.findByText("Indexed 2 chunks.")).toBeDefined();
  const settled = listCalls(calls).length;
  await act(() => vi.advanceTimersByTimeAsync(10_000));
  expect(listCalls(calls)).toHaveLength(settled);
});

test("a rejected upload shows the API message", async () => {
  stubApi((call) =>
    call.method === "POST"
      ? { status: 400, body: { detail: "unsupported file type: .exe" } }
      : { status: 200, body: [] },
  );
  renderDocuments();
  await screen.findByText("No documents yet.");
  const file = new File(["MZ"], "tool.exe");
  fireEvent.change(screen.getByLabelText("Files"), { target: { files: [file] } });
  fireEvent.click(screen.getByRole("button", { name: "Upload documents" }));

  expect((await screen.findByRole("alert")).textContent).toBe("unsupported file type: .exe");
});

test("deleting a document removes it from the list", async () => {
  let deleted = false;
  const calls = stubApi((call) => {
    if (call.method === "DELETE") {
      deleted = true;
      return { status: 204 };
    }
    return {
      status: 200,
      body: deleted ? [] : [document("notes.md", "indexed")],
    };
  });
  renderDocuments();

  fireEvent.click(await screen.findByRole("button", { name: "Delete notes.md" }));

  expect(await screen.findByText("No documents yet.")).toBeDefined();
  const request = calls.find((call) => call.method === "DELETE");
  expect(request?.url).toBe(`${LIST}/id-notes.md`);
  expect(request?.authorization).toBe(`Bearer ${TEST_JWT}`);
});

test("a document that is still indexing cannot be deleted", async () => {
  stubApi(() => ({ status: 200, body: [document("notes.md", "indexing")] }));
  renderDocuments();

  const button = await screen.findByRole("button", { name: "Delete notes.md" });
  expect(button.hasAttribute("disabled")).toBe(true);
});

test("a refused delete shows the API message and keeps the document", async () => {
  stubApi((call) =>
    call.method === "DELETE"
      ? { status: 502, body: { detail: "could not remove indexed chunks" } }
      : { status: 200, body: [document("notes.md", "indexed")] },
  );
  renderDocuments();

  fireEvent.click(await screen.findByRole("button", { name: "Delete notes.md" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "could not remove indexed chunks",
  );
  expect(screen.getByRole("list", { name: "Documents" })).toBeDefined();
});
