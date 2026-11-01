import { expect, test } from "vitest";

import {
  applyHudMessage,
  emptyHud,
  sessionFromResponse,
  sessionPublish,
  sourceLabel,
  transcriptLines,
} from "@/lib/session";

test("session response keeps the livekit url token and room", () => {
  const ready = sessionFromResponse(201, {
    url: "ws://localhost:7880",
    token: "signed-token",
    room: "kb-room",
  });

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

test("hud messages move the preview highlight", () => {
  const thinking = applyHudMessage(emptyHud, '{"kind":"thinking","active":true}');
  expect(thinking.thinking).toBe(true);
  const pointed = applyHudMessage(
    thinking,
    '{"kind":"point","x":1.4,"y":-0.2,"label":" Review status "}',
  );
  expect(pointed.point).toEqual({ x: 1, y: 0, label: "Review status" });
  expect(pointed.thinking).toBe(true);
  expect(applyHudMessage(pointed, "not-json")).toEqual(pointed);
  expect(applyHudMessage(pointed, '{"kind":"thinking","active":false}').thinking).toBe(
    false,
  );
});

test("session errors stay readable", () => {
  expect(sessionFromResponse(404, { detail: "product not found" })).toEqual({
    status: "error",
    message: "Product not found.",
  });
  expect(sessionFromResponse(503, { detail: "LiveKit is not configured" })).toEqual({
    status: "error",
    message: "LiveKit is not configured",
  });
  expect(sessionFromResponse(502, { detail: "Could not dispatch the agent" })).toEqual({
    status: "error",
    message: "Could not dispatch the agent",
  });
  expect(sessionFromResponse(201, { url: "" })).toEqual({
    status: "error",
    message: "Could not start the session.",
  });
});

test("source label uses the file name", () => {
  expect(sourceLabel("file:///docs/billing.md")).toBe("billing.md");
  expect(sourceLabel("upload://notes.md")).toBe("notes.md");
  expect(sourceLabel("notes.md")).toBe("notes.md");
});

test("transcript lines keep short and unbroken text", () => {
  const long = "A".repeat(400);
  const lines = transcriptLines([
    {
      text: "",
      participantInfo: { identity: "user" },
      streamInfo: { id: "empty" },
    },
    {
      text: "A",
      participantInfo: { identity: "user" },
      streamInfo: { id: "one" },
    },
    {
      text: long,
      participantInfo: { identity: "agent-1" },
      streamInfo: { id: "long" },
    },
  ]);

  expect(lines).toEqual([
    { id: "one", speaker: "You", text: "A", sources: [] },
    { id: "long", speaker: "Agent", text: long, sources: [] },
  ]);
});

test("transcript lines keep a cited source and drop an empty line", () => {
  const source = `file:///docs/${"b".repeat(80)}.md`;
  const lines = transcriptLines([
    {
      text: "   ",
      participantInfo: { identity: "agent-1" },
      streamInfo: { id: "blank" },
    },
    {
      text: `Refunds take 5 business days.\nSource: ${source}\nSource: ${source}`,
      participantInfo: { identity: "agent-1" },
      streamInfo: { id: "cited" },
    },
    {
      text: "That is not in the docs.",
      participantInfo: { identity: "agent-1" },
      streamInfo: { id: "missing" },
    },
  ]);

  expect(lines).toEqual([
    {
      id: "cited",
      speaker: "Agent",
      text: "Refunds take 5 business days.",
      sources: [source],
    },
    {
      id: "missing",
      speaker: "Agent",
      text: "That is not in the docs.",
      sources: [],
    },
  ]);
});
