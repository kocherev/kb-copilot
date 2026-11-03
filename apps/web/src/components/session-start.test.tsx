import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { SessionStart } from "@/components/session-start";
import { TEST_JWT, stubApi } from "@/test/api-stub";

vi.mock("@/components/session-room", () => ({
  SessionRoom: ({
    url,
    token,
    onRestart,
  }: {
    url: string;
    token: string;
    onRestart: () => void;
  }) => (
    <div data-url={url} data-token={token}>
      In the room
      <button type="button" onClick={onRestart}>
        New session
      </button>
    </div>
  ),
}));

const productId = "11111111-1111-4111-8111-111111111111";
const grant = { url: "ws://localhost:7880", token: "signed-token", room: "kb-room" };

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("start session posts the product and joins the room", async () => {
  const calls = stubApi(() => ({ status: 201, body: grant }));

  render(
    <SessionStart
      apiUrl="http://localhost:8000"
      productId={productId}
      productName={"A".repeat(80)}
    />,
  );

  const heading = screen.getByRole("heading", { level: 1 });
  expect(heading.textContent).toBe("A".repeat(80));
  expect(heading.className).toMatch(/anywhere/);
  expect(screen.getByRole("link", { name: "Product" }).getAttribute("href")).toBe(
    `/products/${productId}`,
  );

  fireEvent.click(screen.getByRole("button", { name: "Start session" }));

  const room = await screen.findByText("In the room");
  expect(calls).toEqual([
    {
      method: "POST",
      url: "http://localhost:8000/sessions",
      authorization: `Bearer ${TEST_JWT}`,
      json: { product_id: productId },
      form: null,
    },
  ]);
  expect(room.getAttribute("data-url")).toBe("ws://localhost:7880");
  expect(room.getAttribute("data-token")).toBe("signed-token");
});

test("a new session after the room ends goes back to the start button", async () => {
  stubApi(() => ({ status: 201, body: grant }));
  render(
    <SessionStart apiUrl="http://localhost:8000" productId={productId} productName="Acme" />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Start session" }));
  fireEvent.click(await screen.findByRole("button", { name: "New session" }));

  expect(screen.getByRole("button", { name: "Start session" })).toBeDefined();
  expect(screen.queryByText("In the room")).toBeNull();
});

test("a dispatch failure shows the error", async () => {
  stubApi(() => ({ status: 502, body: { detail: "Could not dispatch the agent" } }));
  render(
    <SessionStart apiUrl="http://localhost:8000" productId={productId} productName="Acme" />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Start session" }));

  expect(await screen.findByRole("alert")).toBeDefined();
  expect(screen.getByRole("alert").textContent).toBe("Could not dispatch the agent");
  expect(screen.queryByText("In the room")).toBeNull();
});

test("a refused session shows the error", async () => {
  stubApi(() => ({ status: 404, body: { detail: "product not found" } }));
  render(
    <SessionStart apiUrl="http://localhost:8000" productId={productId} productName="A" />,
  );

  expect(screen.getByRole("heading", { level: 1, name: "A" })).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Start session" }));

  expect(await screen.findByRole("alert")).toBeDefined();
  expect(screen.getByRole("alert").textContent).toBe("Product not found.");
});
