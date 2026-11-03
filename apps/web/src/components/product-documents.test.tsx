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
  render(<ProductDocuments apiUrl="http://localhost:8000" productId={PRODUCT} agentName="Shawn" />);
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
  expect(broken?.textContent).toContain("Failed");
  expect(broken?.textContent).toContain("Could not read this file.");
  expect(notes?.textContent).toContain("Indexed");
  expect(notes?.textContent).toContain("2 sections");
  expect(screen.getByText("1 of 2 indexed, 1 failed.")).toBeDefined();
});

test("says so when there are no documents", async () => {
  stubApi(() => ({ status: 200, body: [] }));
  renderDocuments();

  expect(await screen.findByText("No documents yet")).toBeDefined();
});

test("an API failure shows an error instead of an empty list", async () => {
  stubApi(() => ({ status: 500, body: { detail: "boom" } }));
  renderDocuments();

  expect((await screen.findByRole("alert")).textContent).toContain("Couldn’t load documents.");
  expect(screen.queryByText("No documents yet")).toBeNull();
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
  await screen.findByText("No documents yet");

  expect(screen.queryByRole("button", { name: /^Upload/ })).toBeNull();
  const file = new File(["# Notes"], "notes.md", { type: "text/markdown" });
  fireEvent.change(screen.getByLabelText("Choose files"), { target: { files: [file] } });
  expect(screen.getByRole("list", { name: "Files to upload" }).textContent).toContain("notes.md");
  fireEvent.click(screen.getByRole("button", { name: "Upload 1 file" }));

  expect(await screen.findByText("Indexing")).toBeDefined();
  expect(screen.queryByRole("list", { name: "Files to upload" })).toBeNull();
  const posted = calls.find((call) => call.method === "POST");
  expect(posted?.url).toBe(LIST);
  expect(posted?.authorization).toBe(`Bearer ${TEST_JWT}`);
  expect((posted?.form?.get("files") as File).name).toBe("notes.md");

  await act(() => vi.advanceTimersByTimeAsync(2000));
  await act(() => vi.advanceTimersByTimeAsync(2000));
  expect(await screen.findByText("2 sections")).toBeDefined();
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
  await screen.findByText("No documents yet");
  const file = new File(["MZ"], "tool.exe");
  fireEvent.change(screen.getByLabelText("Choose files"), { target: { files: [file] } });
  fireEvent.click(screen.getByRole("button", { name: "Upload 1 file" }));

  expect((await screen.findByRole("alert")).textContent).toContain("unsupported file type: .exe");
});

test("deleting a document hides it at once and deletes it when the undo runs out", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
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

  expect(screen.queryByRole("list", { name: "Documents" })).toBeNull();
  expect(screen.getByText("Removed notes.md.")).toBeDefined();
  expect(calls.some((call) => call.method === "DELETE")).toBe(false);

  await act(() => vi.advanceTimersByTimeAsync(5000));

  expect(await screen.findByText("No documents yet")).toBeDefined();
  expect(screen.queryByText("Removed notes.md.")).toBeNull();
  const request = calls.find((call) => call.method === "DELETE");
  expect(request?.url).toBe(`${LIST}/id-notes.md`);
  expect(request?.authorization).toBe(`Bearer ${TEST_JWT}`);
});

test("undo brings a removed document back and sends no delete", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const calls = stubApi(() => ({ status: 200, body: [document("notes.md", "indexed")] }));
  renderDocuments();

  fireEvent.click(await screen.findByRole("button", { name: "Delete notes.md" }));
  fireEvent.click(screen.getByRole("button", { name: "Undo" }));
  await act(() => vi.advanceTimersByTimeAsync(10_000));

  expect(screen.getByRole("list", { name: "Documents" }).textContent).toContain("notes.md");
  expect(calls.some((call) => call.method === "DELETE")).toBe(false);
});

test("leaving the page still deletes a document waiting on its undo", async () => {
  const calls = stubApi(() => ({ status: 200, body: [document("notes.md", "indexed")] }));
  const { unmount } = render(
    <ProductDocuments apiUrl="http://localhost:8000" productId={PRODUCT} agentName="Shawn" />,
  );

  fireEvent.click(await screen.findByRole("button", { name: "Delete notes.md" }));
  unmount();

  await vi.waitFor(() =>
    expect(calls.find((call) => call.method === "DELETE")?.url).toBe(`${LIST}/id-notes.md`),
  );
});

test("dropped files wait as chips until uploaded, and can be taken back", async () => {
  stubApi(() => ({ status: 200, body: [] }));
  renderDocuments();
  const zone = (await screen.findByText("No documents yet")).parentElement!;

  const files = [new File(["a"], "a.md"), new File(["b"], "b.md")];
  fireEvent.drop(zone, { dataTransfer: { files } });
  fireEvent.click(screen.getByRole("button", { name: "Remove a.md" }));

  expect(screen.getByRole("list", { name: "Files to upload" }).textContent).not.toContain("a.md");
  expect(screen.getByRole("button", { name: "Upload 1 file" })).toBeDefined();
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

  vi.useFakeTimers({ shouldAdvanceTime: true });
  fireEvent.click(await screen.findByRole("button", { name: "Delete notes.md" }));
  await act(() => vi.advanceTimersByTimeAsync(5000));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "could not remove indexed chunks",
  );
  expect(screen.getByRole("list", { name: "Documents" }).textContent).toContain("notes.md");
});
