import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { SessionStart } from "@/components/session-start";
import { TEST_JWT, stubApi } from "@/test/api-stub";

vi.mock("@/components/session-room", () => ({
  SessionRoom: ({
    url,
    token,
    agentName,
    onRestart,
  }: {
    url: string;
    token: string;
    agentName: string;
    onRestart: () => void;
  }) => (
    <div data-url={url} data-token={token} data-agent={agentName}>
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
      agentName="Mina"
    />,
  );

  const heading = screen.getByRole("heading", { level: 1 });
  expect(heading.textContent).toBe("A".repeat(80));
  expect(heading.className).toMatch(/anywhere/);
  expect(screen.getByRole("link", { name: `Back to ${"A".repeat(80)}` }).getAttribute("href")).toBe(
    `/products/${productId}`,
  );

  fireEvent.click(screen.getByRole("button", { name: "Join session" }));

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
  expect(room.getAttribute("data-agent")).toBe("Mina");
});

test("a new session after the room ends goes back to the join button", async () => {
  stubApi(() => ({ status: 201, body: grant }));
  render(
    <SessionStart apiUrl="http://localhost:8000" productId={productId} productName="Acme" agentName="Mina" />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Join session" }));
  fireEvent.click(await screen.findByRole("button", { name: "New session" }));

  expect(screen.getByRole("button", { name: "Join session" })).toBeDefined();
  expect(screen.queryByText("In the room")).toBeNull();
});

test("a dispatch failure shows the error", async () => {
  stubApi(() => ({ status: 502, body: { detail: "Could not dispatch the agent" } }));
  render(
    <SessionStart apiUrl="http://localhost:8000" productId={productId} productName="Acme" agentName="Mina" />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Join session" }));

  expect(await screen.findByRole("alert")).toBeDefined();
  expect(screen.getByRole("alert").textContent).toBe("Could not dispatch the agent");
  expect(screen.queryByText("In the room")).toBeNull();
});

test("a refused session shows the error", async () => {
  stubApi(() => ({ status: 404, body: { detail: "product not found" } }));
  render(
    <SessionStart apiUrl="http://localhost:8000" productId={productId} productName="A" agentName="Mina" />,
  );

  expect(screen.getByRole("heading", { level: 1, name: "A" })).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Join session" }));

  expect(await screen.findByRole("alert")).toBeDefined();
  expect(screen.getByRole("alert").textContent).toBe("Product not found.");
});

test("the check page warns about a blocked microphone and a browser that can't share", async () => {
  vi.stubGlobal("navigator", {
    permissions: {
      query: async () => ({
        state: "denied",
        addEventListener: () => {},
        removeEventListener: () => {},
      }),
    },
  });
  render(
    <SessionStart apiUrl="http://localhost:8000" productId={productId} productName="Acme" agentName="Mina" />,
  );

  expect(await screen.findByText(/Your browser blocks the microphone/)).toBeDefined();
  expect(screen.getByText(/This browser can't share a screen/)).toBeDefined();
});

test("the check page says what Mina will do when the devices are fine", async () => {
  vi.stubGlobal("navigator", {
    mediaDevices: { getDisplayMedia: async () => null },
    permissions: {
      query: async () => ({
        state: "prompt",
        addEventListener: () => {},
        removeEventListener: () => {},
      }),
    },
  });
  render(
    <SessionStart apiUrl="http://localhost:8000" productId={productId} productName="Acme" agentName="Mina" />,
  );

  expect(await screen.findByText("Mina listens while you talk. You can mute at any time.")).toBeDefined();
  expect(screen.getByText(/Pick a window or a whole screen/)).toBeDefined();
  expect(screen.queryByText(/can't share a screen/)).toBeNull();
});

test("the join button says it is joining while the API answers", async () => {
  let answer: (response: Response) => void = () => {};
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) =>
      String(input) === "/api/auth/token"
        ? Response.json({ token: TEST_JWT })
        : new Promise<Response>((resolve) => {
            answer = resolve;
          }),
    ),
  );
  render(
    <SessionStart apiUrl="http://localhost:8000" productId={productId} productName="Acme" agentName="Mina" />,
  );

  fireEvent.click(screen.getByRole("button", { name: "Join session" }));

  const button = await screen.findByRole("button", { name: "Joining…" });
  expect(button.hasAttribute("disabled")).toBe(true);
  answer(Response.json(grant, { status: 201 }));
  expect(await screen.findByText("In the room")).toBeDefined();
});
