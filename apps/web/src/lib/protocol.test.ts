import { expect, test } from "vitest";

import {
  decisionMessage,
  parseAgentError,
  parseCitations,
  parseComputerMessage,
  parseEscalation,
  parseHudPoint,
} from "@/lib/protocol";

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
  ).toEqual({ kind: "point", x: 1, y: 0, label: "Review status" });
  expect(parseHudPoint('{"kind":"clicking","x":0.2,"y":0.3,"label":"Save"}')).toEqual({
    kind: "clicking",
    x: 0.2,
    y: 0.3,
    label: "Save",
  });
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

test("an escalation needs an id and a title, and keeps the trimmed text", () => {
  expect(
    parseEscalation('{"id":"e1","title":" Cannot reset ","body":" Details\\n"}'),
  ).toEqual({ id: "e1", title: "Cannot reset", body: "Details" });
  expect(parseEscalation('{"id":"","title":"x","body":"y"}')).toBeNull();
  expect(parseEscalation('{"id":"e1","title":"  ","body":"y"}')).toBeNull();
  expect(parseEscalation('{"id":"e1","title":"x"}')).toBeNull();
  expect(parseEscalation("nope")).toBeNull();
});

const proposal = {
  kind: "proposal",
  id: "p1",
  task: "t1",
  description: " Click Update card ",
  x: 0.322,
  y: 0.528,
  needs_approval: true,
  warning: "",
};

test("a proposal keeps its target, or none for a step without one", () => {
  expect(parseComputerMessage(JSON.stringify(proposal))).toEqual({
    kind: "proposal",
    proposal: {
      id: "p1",
      task: "t1",
      description: "Click Update card",
      target: { x: 0.322, y: 0.528 },
      needsApproval: true,
      warning: "",
    },
  });
  const typing = parseComputerMessage(
    JSON.stringify({ ...proposal, x: null, y: null, warning: " Deletes data " }),
  );
  expect(typing?.kind === "proposal" && typing.proposal.target).toBeNull();
  expect(typing?.kind === "proposal" && typing.proposal.warning).toBe("Deletes data");
});

test("an ended task and malformed messages", () => {
  expect(parseComputerMessage('{"kind":"ended","task":"t1","reason":"done"}')).toEqual({
    kind: "ended",
    task: "t1",
  });
  expect(parseComputerMessage(JSON.stringify({ ...proposal, id: "" }))).toBeNull();
  expect(parseComputerMessage(JSON.stringify({ ...proposal, description: " " }))).toBeNull();
  expect(
    parseComputerMessage(JSON.stringify({ ...proposal, needs_approval: "yes" })),
  ).toBeNull();
  expect(parseComputerMessage('{"kind":"ended"}')).toBeNull();
  expect(parseComputerMessage("nope")).toBeNull();
});

test("a decision is the proposal id and the answer", () => {
  expect(JSON.parse(new TextDecoder().decode(decisionMessage("p1", "task")))).toEqual({
    id: "p1",
    decision: "task",
  });
});
