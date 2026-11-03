import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { HandoffCard } from "@/components/handoff-card";
import { TEST_JWT, stubApi } from "@/test/api-stub";

const proposal = {
  id: "11111111-1111-4111-8111-111111111111",
  title: "Customer cannot reset their password",
  body: "Customer cannot reset their password\n\nReason for handoff: SSO",
};
const created = {
  ...proposal,
  status: "created",
  issue_identifier: "ENG-123",
  issue_url: "https://linear.app/acme/issue/ENG-123",
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderCard() {
  render(<HandoffCard apiUrl="http://localhost:8000" agentName="Mina" proposal={proposal} />);
}

test("the card shows the ticket and creates nothing until approved", () => {
  const calls = stubApi(() => ({ status: 200, body: created }));

  renderCard();

  expect(screen.getByRole("heading", { name: proposal.title })).toBeDefined();
  expect(screen.getByText(/Reason for handoff: SSO/)).toBeDefined();
  expect(screen.getByText(/Mina proposes this Linear ticket. Nothing is created until you approve/)).toBeDefined();
  expect(calls).toEqual([]);
});

test("approve calls the API as the user and links the created ticket", async () => {
  const calls = stubApi(() => ({ status: 200, body: created }));
  renderCard();

  fireEvent.click(screen.getByRole("button", { name: "Approve ticket" }));

  const status = await screen.findByRole("status");
  expect(status.textContent).toContain("Ticket ENG-123 created.");
  expect(screen.getByRole("link", { name: "Open in Linear" }).getAttribute("href")).toBe(
    "https://linear.app/acme/issue/ENG-123",
  );
  expect(calls).toHaveLength(1);
  expect(calls[0]?.method).toBe("POST");
  expect(calls[0]?.url).toBe(`http://localhost:8000/escalations/${proposal.id}/approve`);
  expect(calls[0]?.authorization).toBe(`Bearer ${TEST_JWT}`);
  expect(screen.queryByRole("button", { name: "Approve ticket" })).toBeNull();
});

test("dismiss calls the dismiss route and drops the buttons", async () => {
  const calls = stubApi(() => ({ status: 200, body: { ...proposal, status: "dismissed" } }));
  renderCard();

  fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));

  expect((await screen.findByRole("status")).textContent).toBe("Ticket dismissed.");
  expect(calls.map((call) => call.url)).toEqual([
    `http://localhost:8000/escalations/${proposal.id}/dismiss`,
  ]);
  expect(screen.queryByRole("button", { name: "Approve ticket" })).toBeNull();
});

test("a failure keeps the card so the user can try again", async () => {
  stubApi(() => ({ status: 502, body: { detail: "Linear did not create the issue" } }));
  renderCard();

  fireEvent.click(screen.getByRole("button", { name: "Approve ticket" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "Linear did not create the issue",
  );
  expect(screen.getByRole("button", { name: "Approve ticket" })).toBeDefined();
});
