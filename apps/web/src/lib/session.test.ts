import { expect, test } from "vitest";

import {
  sessionFromResponse,
  sessionPublish,
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

test("session errors stay readable", () => {
  expect(sessionFromResponse(404, { detail: "product not found" })).toEqual({
    status: "error",
    message: "Product not found.",
  });
  expect(sessionFromResponse(503, { detail: "LiveKit is not configured" })).toEqual({
    status: "error",
    message: "LiveKit is not configured",
  });
  expect(sessionFromResponse(201, { url: "" })).toEqual({
    status: "error",
    message: "Could not start the session.",
  });
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
    { id: "one", speaker: "You", text: "A" },
    { id: "long", speaker: "Agent", text: long },
  ]);
});
