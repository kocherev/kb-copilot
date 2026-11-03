import { expect, test } from "vitest";

import { median, replayLoad, sessionFacts, stagesOf, timeline, totalMs } from "@/lib/replay";
import { answer, replay } from "@/test/replay-fixture";

test("an unknown or malformed session id is missing, not an error", () => {
  expect(replayLoad(404, undefined, { detail: "session not found" })).toEqual({ status: "missing" });
  expect(replayLoad(422, undefined, { detail: [] })).toEqual({ status: "missing" });
  expect(replayLoad(500, undefined, { detail: "boom" })).toEqual({ status: "error", message: "boom" });
  expect(replayLoad(200, replay, undefined)).toEqual({ status: "ready", replay });
});

test("an agent turn's stages run search, model, audio, and its total is the end to end time", () => {
  const stages = stagesOf(answer);

  expect(stages.map((stage) => [stage.label, stage.ms])).toEqual([
    ["Search", 180],
    ["Model first token", 420],
    ["First audio", 90],
  ]);
  expect(totalMs(answer, stages)).toBe(1100);
  expect(totalMs({ ...answer, latency: { llm_ttft_ms: 420 } }, stages)).toBe(690);
});

test("the timeline puts turns, desktop tasks and handoffs in time order, one task in one place", () => {
  const items = timeline({
    ...replay,
    actions: [
      { event: "proposed", at: "2026-11-03T10:00:10Z", task: "a", detail: "Click Save" },
      { event: "proposed", at: "2026-11-03T10:00:11Z", task: "b", detail: "Open Billing" },
      { event: "performed", at: "2026-11-03T10:00:20Z", task: "a", detail: "Click Save" },
    ],
  });

  expect(items.map((item) => [item.kind, item.at])).toEqual([
    ["turn", "2026-11-03T10:00:05Z"],
    ["turn", "2026-11-03T10:00:09Z"],
    ["task", "2026-11-03T10:00:10Z"],
    ["task", "2026-11-03T10:00:11Z"],
    ["handoff", "2026-11-03T10:01:30Z"],
  ]);
  const [, , first] = items;
  expect(first?.kind === "task" && first.steps.map((step) => step.event)).toEqual([
    "proposed",
    "performed",
  ]);
});

test("median takes the middle value, or the mean of the two middle ones", () => {
  expect(median([])).toBeNull();
  expect(median([900, 300, 1200])).toBe(900);
  expect(median([1000, 300, 1200, 400])).toBe(700);
});

test("session facts leave out counts of nothing except turns", () => {
  expect(sessionFacts(replay)).toEqual(["2:05", "2 turns", "1 desktop action", "1 handoff"]);
  expect(
    sessionFacts({ ...replay, ended_at: null, turn_count: 0, action_count: 0, handoff_count: 0 }),
  ).toEqual(["0 turns"]);
});
