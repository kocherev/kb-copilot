import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ProductSessions } from "@/components/product-sessions";
import { stubApi } from "@/test/api-stub";
import { replay } from "@/test/replay-fixture";

const PRODUCT = replay.product_id;

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderSessions() {
  render(<ProductSessions apiUrl="http://localhost:8000" productId={PRODUCT} agentName="Shawn" />);
}

test("lists this product's sessions with date, length and counts, each a link", async () => {
  const calls = stubApi(() => ({ status: 200, body: [replay] }));
  renderSessions();

  const list = await screen.findByRole("list", { name: "Sessions" });
  const link = within(list).getByRole("link", { name: /^Nov 3, 2026, 10:00 AM UTC/ });
  expect(link.getAttribute("href")).toBe(`/products/${PRODUCT}/sessions/s1`);
  expect(link.textContent).toContain("2:05·2 turns·1 desktop action·1 handoff");
  const sessionsCall = calls.find((call) => call.url.includes("/sessions"));
  expect(sessionsCall?.url).toBe(`http://localhost:8000/sessions?product_id=${PRODUCT}`);
});

test("says so when there are no sessions yet", async () => {
  stubApi(() => ({ status: 200, body: [] }));
  renderSessions();

  expect(await screen.findByText(/No sessions yet/)).toBeDefined();
});

test("an API failure shows an error that can try again", async () => {
  let failing = true;
  stubApi(() => (failing ? { status: 500, body: { detail: "boom" } } : { status: 200, body: [replay] }));
  renderSessions();

  expect((await screen.findByRole("alert")).textContent).toContain("Couldn’t load sessions.");
  expect(screen.queryByText(/No sessions yet/)).toBeNull();

  failing = false;
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("list", { name: "Sessions" })).toBeDefined();
  expect(screen.queryByRole("alert")).toBeNull();
});

test("says it is loading until the list arrives", async () => {
  stubApi(() => ({ status: 200, body: [] }));
  renderSessions();

  expect(screen.getByRole("status").textContent).toBe("Loading sessions");
  await screen.findByText(/No sessions yet/);
});
