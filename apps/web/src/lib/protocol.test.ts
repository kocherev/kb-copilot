import { expect, test } from "vitest";

import { parseAgentError, parseCitations, parseHudPoint } from "@/lib/protocol";

const passage = {
  id: "p1",
  title: "Refund timing",
  source: "billing/refunds.md",
  anchor: "refund-timing",
  snippet: "Refunds take 5 business days.",
};

test("a highlight is clamped to the frame and needs a label", () => {
  expect(
    parseHudPoint('{"kind":"point","x":1.4,"y":-0.2,"label":" Review status "}'),
  ).toEqual({ x: 1, y: 0, label: "Review status" });
  expect(parseHudPoint('{"kind":"point","x":0.5,"y":0.5,"label":"  "}')).toBeNull();
  expect(parseHudPoint('{"kind":"point","x":"0.5","y":0.5,"label":"Go"}')).toBeNull();
  expect(parseHudPoint('{"kind":"thinking","active":true}')).toBeNull();
  expect(parseHudPoint("not-json")).toBeNull();
});

test("citations keep the message text and every passage field", () => {
  const raw = JSON.stringify({ message_id: "m1", text: "Hi.", passages: [passage] });

  expect(parseCitations(raw)).toEqual({
    messageId: "m1",
    text: "Hi.",
    passages: [passage],
  });
  expect(parseCitations(JSON.stringify({ message_id: "m1", text: "x", passages: [] }))).toBeNull();
  expect(
    parseCitations(
      JSON.stringify({ message_id: "m1", text: "x", passages: [{ ...passage, id: 4 }] }),
    ),
  ).toBeNull();
  expect(parseCitations("[]")).toBeNull();
});

test("an agent error is its trimmed message", () => {
  expect(parseAgentError('{"message":" Could not start "}')).toBe("Could not start");
  expect(parseAgentError('{"message":""}')).toBeNull();
  expect(parseAgentError("nope")).toBeNull();
});
