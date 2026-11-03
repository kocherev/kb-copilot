import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Activity } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { HomePage, type HomeData } from "@/components/home-page";
import { TEST_JWT, stubApi } from "@/test/api-stub";

const router = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));

vi.mock("next/navigation", () => ({ useRouter: () => router }));

const draft = {
  name: "Acme",
  description: "Acme helps customers reset passwords.",
  tone: "calm and brief",
  refusal_rules: "Do not invent a refund policy.",
  agent_name: "Mina",
  voice: "Achird" as const,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

const productId = "11111111-1111-4111-8111-111111111111";
const empty: HomeData = { products: [], documentCounts: {}, sessions: [] };

function openCreateForm() {
  fireEvent.click(screen.getAllByRole("button", { name: "New product" })[0]);
}

function fillCreateForm() {
  openCreateForm();
  fireEvent.change(screen.getByLabelText("Name"), {
    target: { value: draft.name },
  });
  fireEvent.change(screen.getByLabelText("Description"), {
    target: { value: draft.description },
  });
  fireEvent.change(screen.getByLabelText("Tone"), {
    target: { value: draft.tone },
  });
  fireEvent.change(screen.getByLabelText("Refusal rules"), {
    target: { value: draft.refusal_rules },
  });
  fireEvent.change(screen.getByLabelText("Agent name"), {
    target: { value: draft.agent_name },
  });
  fireEvent.change(screen.getByLabelText("Voice"), { target: { value: draft.voice } });
}

test("home page explains the product and offers a first product", () => {
  render(<HomePage apiUrl="http://localhost:8000/" data={empty} />);

  expect(screen.getByRole("heading", { level: 1, name: "Products" })).toBeDefined();
  expect(screen.queryByRole("link", { name: "API health" })).toBeNull();
  expect(screen.getByText(/answers out loud/i)).toBeDefined();
  expect(screen.getByText("Set up your first product")).toBeDefined();
  expect(screen.getAllByRole("button", { name: "New product" })).toHaveLength(2);
});

function session(product_id: string, created_at: string) {
  return {
    id: created_at,
    product_id,
    room: "r",
    user_id: null,
    created_at,
    ended_at: null,
    turn_count: 0,
    action_count: 0,
    handoff_count: 0,
  };
}

test("each product is a card with its documents and latest session", () => {
  const otherId = "22222222-2222-4222-8222-222222222222";
  const data: HomeData = {
    products: [
      { id: productId, ...draft },
      { id: otherId, ...draft, name: "Ledgerly" },
    ],
    documentCounts: { [productId]: 6, [otherId]: 0 },
    sessions: [
      session(productId, "2026-11-01T10:00:00Z"),
      session(productId, "2026-11-03T08:00:00Z"),
      session(productId, "2026-11-02T23:00:00Z"),
    ],
  };
  render(<HomePage apiUrl="http://localhost:8000" data={data} />);

  expect(screen.getByRole("link", { name: "Acme" }).getAttribute("href")).toBe(
    `/products/${productId}`,
  );
  expect(screen.getByText("6 documents")).toBeDefined();
  expect(screen.getByText("Last session Nov 3")).toBeDefined();
  expect(screen.getByText("No documents yet")).toBeDefined();
  expect(screen.getByText("No sessions yet")).toBeDefined();
  expect(screen.getAllByText("Mina, Achird voice")).toHaveLength(2);
});

test("the product list shows a skeleton while it loads", () => {
  render(<HomePage apiUrl="http://localhost:8000" />);

  expect(screen.getByRole("status").textContent).toBe("Loading products");
  expect(screen.getByRole("button", { name: "New product" })).toBeDefined();
});

test("a failed product list says what to do and can try again", () => {
  render(<HomePage apiUrl="http://localhost:8000" data={null} />);

  expect(screen.getByRole("alert").textContent).toContain("Couldn’t load your products");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(router.refresh).toHaveBeenCalledOnce();
});

test("creating a product opens it", async () => {
  const created = { id: productId, ...draft };
  const calls = stubApi(() => ({ status: 201, body: created }));
  render(<HomePage apiUrl="http://localhost:8000" data={empty} />);
  fillCreateForm();
  expect(screen.getByRole("dialog", { name: "New product" })).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));

  await vi.waitFor(() => expect(router.push).toHaveBeenCalledWith(`/products/${created.id}`));
  expect(calls).toMatchObject([
    {
      method: "POST",
      url: "http://localhost:8000/products",
      authorization: `Bearer ${TEST_JWT}`,
      json: draft,
    },
  ]);
});

test("the create button says it is working until the API answers", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      String(input) === "/api/auth/token"
        ? Promise.resolve(Response.json({ token: TEST_JWT }))
        : new Promise<Response>(() => {}),
    ),
  );
  render(<HomePage apiUrl="http://localhost:8000" data={empty} />);
  fillCreateForm();
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));

  const pending = await screen.findByRole("button", { name: "Creating product…" });
  expect(pending.getAttribute("aria-disabled")).toBe("true");
  expect(screen.getByRole("form", { name: "Create product" }).getAttribute("aria-busy")).toBe(
    "true",
  );
});

test("a finished create clears when the page hides", async () => {
  stubApi(() => ({ status: 201, body: { id: productId, ...draft } }));
  function Page({ hidden }: { hidden: boolean }) {
    return (
      <Activity mode={hidden ? "hidden" : "visible"}>
        <HomePage apiUrl="http://localhost:8000" data={empty} />
      </Activity>
    );
  }
  const view = render(<Page hidden={false} />);
  fillCreateForm();
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));
  await vi.waitFor(() => expect(router.push).toHaveBeenCalled());

  view.rerender(<Page hidden />);
  view.rerender(<Page hidden={false} />);
  openCreateForm();

  expect(screen.getByLabelText("Name")).toHaveProperty("value", "");
  expect(screen.getByLabelText("Description")).toHaveProperty("value", "");
  expect(screen.getByLabelText("Agent name")).toHaveProperty("value", "Shawn");
  expect(screen.getByLabelText("Voice")).toHaveProperty("value", "Sulafat");
  expect(screen.queryByText("Saved")).toBeNull();
});

test("an unfinished draft stays when the sheet closes and the page hides", () => {
  function Page({ hidden }: { hidden: boolean }) {
    return (
      <Activity mode={hidden ? "hidden" : "visible"}>
        <HomePage apiUrl="http://localhost:8000" data={empty} />
      </Activity>
    );
  }
  const view = render(<Page hidden={false} />);
  openCreateForm();
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Acme" } });
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  view.rerender(<Page hidden />);
  view.rerender(<Page hidden={false} />);
  openCreateForm();
  expect(screen.getByLabelText("Name")).toHaveProperty("value", "Acme");
});

test("create shows the api error", async () => {
  stubApi(() => ({
    status: 422,
    body: {
      detail: [
        { loc: ["body", "description"], msg: "String should match pattern", type: "x" },
      ],
    },
  }));
  render(<HomePage apiUrl="http://localhost:8000" data={empty} />);
  fillCreateForm();
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "description: String should match pattern",
  );
});

test("create survives a response that is not a product", async () => {
  stubApi(() => ({ status: 201, text: "not json" }));
  render(<HomePage apiUrl="http://localhost:8000" data={empty} />);
  fillCreateForm();
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "Couldn’t save the product. Check your connection and try again.",
  );
});

test("a description typed on several lines is saved as one paragraph", async () => {
  stubApi((call) => {
    const sent = call.json as typeof draft;
    if (/[\r\n]/.test(sent.description)) {
      return { status: 422, body: { detail: [{ loc: ["body", "description"], msg: "x" }] } };
    }
    return { status: 201, body: { id: productId, ...sent } };
  });
  render(<HomePage apiUrl="http://localhost:8000" data={empty} />);
  fillCreateForm();
  fireEvent.change(screen.getByLabelText("Description"), {
    target: { value: "Acme resets passwords.\r\n\n  It also unlocks accounts." },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));

  await vi.waitFor(() => expect(router.push).toHaveBeenCalled());
  openCreateForm();
  expect(screen.getByLabelText("Description")).toHaveProperty(
    "value",
    "Acme resets passwords. It also unlocks accounts.",
  );
});
