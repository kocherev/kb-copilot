import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Activity } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { HomePage } from "@/components/home-page";
import { TEST_JWT, stubApi } from "@/test/api-stub";

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
  fireEvent.change(screen.getByLabelText("Agent name"), {
    target: { value: draft.agent_name },
  });
  fireEvent.change(screen.getByLabelText("Voice"), { target: { value: draft.voice } });
}

test("home page explains the flow without operator links", () => {
  render(<HomePage apiUrl="http://localhost:8000/" products={[]} />);

  expect(
    screen.getByRole("heading", { level: 1, name: "Knowledge base copilot" }),
  ).toBeDefined();
  expect(screen.queryByRole("link", { name: "API health" })).toBeNull();
  expect(screen.getByText(/answers by voice/i)).toBeDefined();
  expect(screen.getByRole("button", { name: "Create product" })).toBeDefined();
  expect(screen.getByText("No products yet.")).toBeDefined();
});

test("home page links each product in the org", () => {
  render(
    <HomePage
      apiUrl="http://localhost:8000"
      products={[{ id: "11111111-1111-4111-8111-111111111111", ...draft }]}
    />,
  );

  expect(screen.getByRole("link", { name: "Acme" }).getAttribute("href")).toBe(
    "/products/11111111-1111-4111-8111-111111111111",
  );
});

test("a failed product list says so", () => {
  render(<HomePage apiUrl="http://localhost:8000" products={null} />);

  expect(screen.getByRole("alert").textContent).toBe("Could not load products.");
});

test("creating a product shows that it was saved", async () => {
  const created = {
    id: "11111111-1111-4111-8111-111111111111",
    ...draft,
  };
  const calls = stubApi(() => ({ status: 201, body: created }));
  render(<HomePage apiUrl="http://localhost:8000" products={[]} />);
  fillCreateForm();
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));

  expect(await screen.findByRole("status")).toBeDefined();
  expect(screen.getByRole("status").textContent).toBe("Saved");
  expect(calls).toMatchObject([
    {
      method: "POST",
      url: "http://localhost:8000/products",
      authorization: `Bearer ${TEST_JWT}`,
      json: draft,
    },
  ]);
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
  stubApi(() => ({ status: 201, body: created }));
  function Page({ hidden }: { hidden: boolean }) {
    return (
      <Activity mode={hidden ? "hidden" : "visible"}>
        <HomePage apiUrl="http://localhost:8000" products={[]} />
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
  expect(screen.getByLabelText("Agent name")).toHaveProperty("value", "Shawn");
  expect(screen.getByLabelText("Voice")).toHaveProperty("value", "Sulafat");
  expect(screen.queryByText("Saved")).toBeNull();
  expect(screen.queryByRole("link", { name: "Open Acme" })).toBeNull();
});

test("an unfinished draft stays when the page hides", () => {
  function Page({ hidden }: { hidden: boolean }) {
    return (
      <Activity mode={hidden ? "hidden" : "visible"}>
        <HomePage apiUrl="http://localhost:8000" products={[]} />
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
  stubApi(() => ({
    status: 422,
    body: {
      detail: [
        { loc: ["body", "description"], msg: "String should match pattern", type: "x" },
      ],
    },
  }));
  render(<HomePage apiUrl="http://localhost:8000" products={[]} />);
  fillCreateForm();
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "description: String should match pattern",
  );
});

test("create survives a response that is not a product", async () => {
  stubApi(() => ({ status: 201, text: "not json" }));
  render(<HomePage apiUrl="http://localhost:8000" products={[]} />);
  fillCreateForm();
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "Could not save the product.",
  );
});

test("a description typed on several lines is saved as one paragraph", async () => {
  stubApi((call) => {
    const sent = call.json as typeof draft;
    if (/[\r\n]/.test(sent.description)) {
      return { status: 422, body: { detail: [{ loc: ["body", "description"], msg: "x" }] } };
    }
    return { status: 201, body: { id: "11111111-1111-4111-8111-111111111111", ...sent } };
  });
  render(<HomePage apiUrl="http://localhost:8000" products={[]} />);
  fillCreateForm();
  fireEvent.change(screen.getByLabelText("Description"), {
    target: { value: "Acme resets passwords.\r\n\n  It also unlocks accounts." },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create product" }));

  expect((await screen.findByRole("status")).textContent).toBe("Saved");
  expect(screen.getByLabelText("Description")).toHaveProperty(
    "value",
    "Acme resets passwords. It also unlocks accounts.",
  );
});
