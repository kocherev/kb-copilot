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

function stat(label: string): string | null | undefined {
  return screen.getByText(label).nextElementSibling?.textContent;
}

test("the header gives the start, and the stats sum up the session", () => {
  show();

  expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Nov 3, 2026, 10:00 AM UTC");
  expect(screen.getByText("Room kb-room")).toBeDefined();
  expect(stat("Length")).toBe("2:052 turns");
  expect(stat("Median reply")).toBe("1.1 sover 1 answer");
  expect(stat("Searches")).toBe("1");
  expect(stat("Desktop")).toBe("1step done, 1 handoff");
  expect(screen.getByRole("link", { name: "Acme" }).getAttribute("href")).toBe(
    `/products/${replay.product_id}`,
  );
});

test("the transcript shows who said what and when", () => {
  show();

  const timeline = screen.getByRole("list", { name: "Timeline" });
  const [first, second, task, handoff] = Array.from(timeline.children);
  expect(first?.textContent).toContain("You+0:05");
  expect(first?.textContent).toContain("How do I reset my password?");
  expect(second?.textContent).toContain("Shawn+0:09Replied in 1.1 s");
  expect(second?.textContent).toContain("Open Settings, then Security.");
  expect(task?.textContent).toContain("Desktop task+1:00");
  expect(handoff?.textContent).toContain("Handed to a person+1:30");
});

test("an answer lists what it searched, with scores, and what it cited", () => {
  show();

  const searches = screen.getByRole("list", { name: "Searches" });
  expect(searches.textContent).toContain("Searched “reset password”");
  expect(searches.textContent).toContain("180 ms");
  const passages = within(searches).getAllByRole("listitem").slice(1);
  expect(passages.map((passage) => passage.textContent)).toEqual([
    "1Reset a passwordCitedreset.md0.91",
    "2Rolesreset.md0.42",
  ]);
  const cited = screen.getByRole("list", { name: "Cited" });
  expect(cited.textContent).toBe("Reset a passwordreset.md");
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

  const search = screen.getByRole("list", { name: "Searches" });
  expect(search.textContent).toContain("“moon base”No match90 ms");
  expect(screen.getByText("No passage scored high enough to answer from.")).toBeDefined();
  expect(screen.getByText("No passage came back.")).toBeDefined();
  expect(screen.queryByRole("list", { name: "Cited" })).toBeNull();
});

test("each latency row links to its turn in the timeline", () => {
  show();

  const rows = within(screen.getByRole("list", { name: "Latency by turn" })).getAllByRole("link");
  expect(rows.map((row) => row.getAttribute("href"))).toEqual(["#turn-t1", "#turn-t2"]);
  expect(document.getElementById("turn-t2")?.textContent).toContain("Open Settings");
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
  expect(screen.getByText("Cannot reset password").parentElement?.textContent).toBe(
    "Cannot reset passwordcreatedENG-7",
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

  expect(screen.getByText("Nothing to replay")).toBeDefined();
  expect(screen.getByRole("link", { name: "Start a session" }).getAttribute("href")).toBe(
    `/products/${replay.product_id}/session`,
  );
  expect(screen.queryByRole("heading", { name: "Timeline" })).toBeNull();
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
