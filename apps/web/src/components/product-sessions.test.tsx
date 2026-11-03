import { cleanup, render, screen, within } from "@testing-library/react";
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
  render(<ProductSessions apiUrl="http://localhost:8000" productId={PRODUCT} />);
}

test("lists this product's sessions with date, length and counts, each a link", async () => {
  const calls = stubApi(() => ({ status: 200, body: [replay] }));
  renderSessions();

  const list = await screen.findByRole("list", { name: "Sessions" });
  const link = within(list).getByRole("link", { name: "Nov 3, 2026, 10:00 AM UTC" });
  expect(link.getAttribute("href")).toBe(`/products/${PRODUCT}/sessions/s1`);
  expect(list.textContent).toContain("2:05, 2 turns, 1 action, 1 handoff");
  const sessionsCall = calls.find((call) => call.url.includes("/sessions"));
  expect(sessionsCall?.url).toBe(`http://localhost:8000/sessions?product_id=${PRODUCT}`);
});

test("says so when there are no sessions yet", async () => {
  stubApi(() => ({ status: 200, body: [] }));
  renderSessions();

  expect(await screen.findByText(/No sessions yet/)).toBeDefined();
});

test("an API failure shows an error instead of an empty list", async () => {
  stubApi(() => ({ status: 500, body: { detail: "boom" } }));
  renderSessions();

  expect((await screen.findByRole("alert")).textContent).toBe("Could not load sessions.");
  expect(screen.queryByText(/No sessions yet/)).toBeNull();
});

test("shows a loading line until the list arrives", async () => {
  stubApi(() => ({ status: 200, body: [] }));
  renderSessions();

  expect(screen.getByText("Loading sessions.")).toBeDefined();
  await screen.findByText(/No sessions yet/);
});
