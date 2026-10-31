import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Activity } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { HomePage } from "@/components/home-page";

const draft = {
  name: "Acme",
  description: "Acme helps customers reset passwords.",
  tone: "calm and brief",
  refusal_rules: "Do not invent a refund policy.",
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function fillCreateForm() {
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
}

test("home page links to api health", () => {
  render(<HomePage apiUrl="http://localhost:8000/" />);

  expect(
    screen.getByRole("heading", { level: 1, name: "Knowledge base copilot" }),
  ).toBeDefined();
  expect(screen.getByRole("link", { name: "API health" }).getAttribute("href")).toBe(
    "http://localhost:8000/health",
  );
  expect(screen.getByText(/answers by voice/i)).toBeDefined();
  expect(screen.getByRole("button", { name: "Create product" })).toBeDefined();
});

test("creating a product shows that it was saved", async () => {
  const created = {
    id: "11111111-1111-4111-8111-111111111111",
    ...draft,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("http://localhost:8000/products");
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toEqual(draft);
      return {
        ok: true,
        status: 201,
        json: async () => created,
      };
    }),
  );
  render(<HomePage apiUrl="http://localhost:8000" />);
  fillCreateForm();
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));

  expect(await screen.findByRole("status")).toBeDefined();
  expect(screen.getByRole("status").textContent).toBe("Saved");
  expect(screen.getByRole("link", { name: "Open Acme" }).getAttribute("href")).toBe(
    `/products/${created.id}`,
  );
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Acme Care" } });
  expect(screen.queryByText("Saved")).toBeNull();
});

test("a finished create clears when the page hides", async () => {
  const created = {
    id: "11111111-1111-4111-8111-111111111111",
    ...draft,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      status: 201,
      json: async () => created,
    })),
  );
  function Page({ hidden }: { hidden: boolean }) {
    return (
      <Activity mode={hidden ? "hidden" : "visible"}>
        <HomePage apiUrl="http://localhost:8000" />
      </Activity>
    );
  }
  const view = render(<Page hidden={false} />);
  fillCreateForm();
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));
  expect(await screen.findByText("Saved")).toBeDefined();

  view.rerender(<Page hidden />);
  view.rerender(<Page hidden={false} />);

  expect(screen.getByLabelText("Name")).toHaveProperty("value", "");
  expect(screen.getByLabelText("Description")).toHaveProperty("value", "");
  expect(screen.queryByText("Saved")).toBeNull();
  expect(screen.queryByRole("link", { name: "Open Acme" })).toBeNull();
});

test("an unfinished draft stays when the page hides", () => {
  function Page({ hidden }: { hidden: boolean }) {
    return (
      <Activity mode={hidden ? "hidden" : "visible"}>
        <HomePage apiUrl="http://localhost:8000" />
      </Activity>
    );
  }
  const view = render(<Page hidden={false} />);
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Acme" } });
  view.rerender(<Page hidden />);
  view.rerender(<Page hidden={false} />);
  expect(screen.getByLabelText("Name")).toHaveProperty("value", "Acme");
});

test("create shows the api error", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      status: 400,
      json: async () => ({ detail: "description must be one paragraph" }),
    })),
  );
  render(<HomePage apiUrl="http://localhost:8000" />);
  fillCreateForm();
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));

  expect((await screen.findByRole("alert")).textContent).toContain("one paragraph");
});

test("create survives a response that is not a product", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      status: 201,
      json: async () => {
        throw new Error("not json");
      },
    })),
  );
  render(<HomePage apiUrl="http://localhost:8000" />);
  fillCreateForm();
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "Could not save the product.",
  );
});
