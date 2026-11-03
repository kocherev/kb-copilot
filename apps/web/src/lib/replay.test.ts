import { expect, test } from "vitest";

import { replayLoad, stagesOf, totalMs } from "@/lib/replay";
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
