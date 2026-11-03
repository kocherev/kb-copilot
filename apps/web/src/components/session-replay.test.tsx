import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { SessionReplay } from "@/components/session-replay";
import { replay } from "@/test/replay-fixture";

afterEach(cleanup);

function show(value = replay) {
  render(
    <SessionReplay
      replay={value}
      productId={value.product_id}
      productName="Acme"
      agentName="Shawn"
    />,
  );
}

test("the header gives the start, length and counts", () => {
  show();

  expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Nov 3, 2026, 10:00 AM UTC");
  expect(screen.getByText("2:05, 2 turns, 1 action, 1 handoff")).toBeDefined();
  expect(screen.getByRole("link", { name: "Acme" }).getAttribute("href")).toBe(
    `/products/${replay.product_id}`,
  );
});

test("the transcript shows who said what and when", () => {
  show();

  const [first, second] = within(screen.getByRole("list", { name: "Turns" })).getAllByRole(
    "listitem",
  );
  expect(first?.textContent).toContain("You+0:05");
  expect(first?.textContent).toContain("How do I reset my password?");
  expect(second?.textContent).toContain("Shawn+0:09");
  expect(second?.textContent).toContain("Open Settings, then Security.");
});

test("an answer lists what it searched, with scores, and what it cited", () => {
  show();

  const searches = screen.getByRole("list", { name: "Searches" });
  expect(searches.textContent).toContain("Searched for “reset password”");
  expect(searches.textContent).toContain("(180 ms)");
  expect(searches.textContent).toContain("Reset a password");
  expect(searches.textContent).toContain("0.91");
  expect(searches.textContent).toContain("Roles");
  expect(searches.textContent).toContain("0.42");
  const cited = screen.getByRole("list", { name: "Cited" });
  expect(cited.textContent).toBe("Cited Reset a password (reset.md)");
});

test("a search that found nothing says so", () => {
  const [question, answer] = replay.turns;
  const abstained = {
    query: "moon base",
    passages: [],
    abstained: true,
    duration_ms: 90,
  };
  show({
    ...replay,
    turns: [question!, { ...answer!, searches: [abstained], citations: [] }],
  });

  expect(screen.getByText(/Searched for “moon base”/).textContent).toContain("no match, 90 ms");
  expect(screen.getByText("No passage came back.")).toBeDefined();
  expect(screen.queryByRole("list", { name: "Cited" })).toBeNull();
});

test("the waterfall shows each stage of each turn with its time", () => {
  show();

  const bars = within(screen.getByRole("list", { name: "Latency by turn" })).getAllByRole("img");
  expect(bars.map((bar) => bar.getAttribute("aria-label"))).toEqual([
    "End of turn 300 ms, Transcript 120 ms",
    "Search 180 ms, Model first token 420 ms, First audio 90 ms",
  ]);
  const rows = screen.getByRole("list", { name: "Latency by turn" }).textContent;
  expect(rows).toContain("Turn 1, You420 ms");
  expect(rows).toContain("Turn 2, Shawn1.1 s");
});

test("the desktop steps and handoffs of the session are listed", () => {
  show();

  const steps = within(screen.getByRole("list", { name: "Desktop actions" })).getAllByRole(
    "listitem",
  );
  expect(steps.map((step) => step.textContent)).toEqual([
    "+1:00ProposedClick Save",
    "+1:05DoneClick Save",
  ]);
  expect(screen.getByRole("list", { name: "Handoffs" }).textContent).toBe(
    "Cannot reset password (created, ENG-7)",
  );
});

test("a session nobody spoke in says there is nothing to replay", () => {
  show({
    ...replay,
    ended_at: null,
    turn_count: 0,
    action_count: 0,
    handoff_count: 0,
    turns: [],
    actions: [],
    handoffs: [],
  });

  expect(screen.getByText("Nothing was said in this session, so there is nothing to replay.")).toBeDefined();
  expect(screen.getByText("0 turns, 0 actions, 0 handoffs")).toBeDefined();
  expect(screen.queryByRole("heading", { name: "Transcript" })).toBeNull();
  expect(screen.queryByRole("heading", { name: "Latency" })).toBeNull();
});

test("turns without timings still replay, with an empty latency note", () => {
  const [question, answer] = replay.turns;
  show({
    ...replay,
    turns: [
      { ...question!, latency: {} },
      { ...answer!, latency: {}, searches: [] },
    ],
  });

  expect(screen.getByText("No latency was measured for this session.")).toBeDefined();
  expect(screen.getByText("Open Settings, then Security.")).toBeDefined();
});
