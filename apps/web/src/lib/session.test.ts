import { expect, test } from "vitest";

import {
  connectionLabel,
  sessionLoad,
  sessionPublish,
  sourceLabel,
  transcriptLines,
} from "@/lib/session";

test("session response keeps the livekit url token and room", () => {
  const ready = sessionLoad(
    201,
    { url: "ws://localhost:7880", token: "signed-token", room: "kb-room" },
    undefined,
  );

  expect(ready).toEqual({
    status: "ready",
    session: {
      url: "ws://localhost:7880",
      token: "signed-token",
      room: "kb-room",
    },
  });
  expect(sessionPublish).toEqual({ audio: true, video: false, screen: true });
});

test("session errors stay readable", () => {
  expect(sessionLoad(404, undefined, { detail: "product not found" })).toEqual({
    status: "error",
    message: "Product not found.",
  });
  expect(sessionLoad(503, undefined, { detail: "LiveKit is not configured" })).toEqual({
    status: "error",
    message: "LiveKit is not configured",
  });
  expect(
    sessionLoad(429, undefined, { detail: "too many sessions, try again shortly" }),
  ).toEqual({ status: "error", message: "too many sessions, try again shortly" });
  expect(sessionLoad(500, undefined, null)).toEqual({
    status: "error",
    message: "Could not start the session.",
  });
});

test("source label uses the file name", () => {
  expect(sourceLabel("file:///docs/billing.md")).toBe("billing.md");
  expect(sourceLabel("upload://notes.md")).toBe("notes.md");
  expect(sourceLabel("notes.md")).toBe("notes.md");
});

const passage = {
  id: "p1",
  title: "Refund timing",
  source: "billing/refunds.md",
  anchor: "refund-timing",
  snippet: "Refunds take five business days.",
};

function item(id: string, identity: string, text: string) {
  return { text, participantInfo: { identity }, streamInfo: { id } };
}

test("transcript lines keep short and unbroken text and drop blanks", () => {
  const long = "A".repeat(400);

  const lines = transcriptLines([
    item("empty", "user", ""),
    item("blank", "agent-1", "   "),
    item("one", "user:user-a", "A"),
    item("long", "agent-1", long),
  ]);

  expect(lines).toEqual([
    { id: "one", speaker: "You", text: "A", citations: [] },
    { id: "long", speaker: "Agent", text: long, citations: [] },
  ]);
});

test("a citations message attaches to the agent line with the same text", () => {
  const citations = [
    { messageId: "m1", text: "Refunds take  five business days.", passages: [passage] },
  ];

  const lines = transcriptLines(
    [
      item("a", "user", "Refunds take five business days."),
      item("b", "agent-1", "Refunds take five\nbusiness days. "),
      item("c", "agent-1", "That is not in the docs."),
    ],
    citations,
  );

  expect(lines.map((line) => line.citations)).toEqual([[], [passage], []]);
});

test("every connection state has a plain label", () => {
  expect(
    ["connecting", "connected", "reconnecting", "signalReconnecting", "disconnected"].map(
      connectionLabel,
    ),
  ).toEqual([
    "Connecting",
    "In the room",
    "Connection lost. Reconnecting",
    "Connection lost. Reconnecting",
    "Session ended",
  ]);
});
