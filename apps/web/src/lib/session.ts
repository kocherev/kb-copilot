import { errorDetail, type SessionGrant } from "@/lib/api/client";
import type { Citations, CitedPassage } from "@/lib/protocol";

export type SessionLoad =
  | { status: "ready"; session: SessionGrant }
  | { status: "error"; message: string };

export type TranscriptLine = {
  id: string;
  speaker: string;
  text: string;
  citations: CitedPassage[];
};

export const sessionPublish = {
  audio: true,
  video: false,
  screen: true,
} as const;

export function sessionLoad(
  status: number,
  session: SessionGrant | undefined,
  error: unknown,
): SessionLoad {
  if (status === 404) {
    return { status: "error", message: "Product not found." };
  }
  if (session === undefined) {
    return { status: "error", message: errorDetail(error, "Could not start the session.") };
  }
  return { status: "ready", session };
}

// LiveKit names agent participants agent-<id>. Everyone else is the caller.
function speakerLabel(identity: string): string {
  return identity.startsWith("agent-") ? "Agent" : "You";
}

export function sourceLabel(source: string): string {
  const cleaned = source.trim();
  const upload = /^upload:\/\/(.+)$/.exec(cleaned);
  if (upload?.[1]) {
    return upload[1];
  }
  const path = cleaned.split("?")[0]?.replace(/\/+$/, "") ?? cleaned;
  const name = path.split("/").pop();
  return name && name.length > 0 ? name : cleaned;
}

// The values of livekit-client's ConnectionState.
export function connectionLabel(state: string): string {
  switch (state) {
    case "connected":
      return "In the room";
    case "reconnecting":
    case "signalReconnecting":
      return "Connection lost. Reconnecting";
    case "disconnected":
      return "Session ended";
    default:
      return "Connecting";
  }
}

function normalized(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

// A citations message names the assistant message it supports by its text.
// The transcript stream ids are not message ids, so the text is the join key.
export function transcriptLines(
  items: {
    text: string;
    participantInfo: { identity: string };
    streamInfo: { id: string };
  }[],
  citations: Citations[] = [],
): TranscriptLine[] {
  const byText = new Map(
    citations.map((found) => [normalized(found.text), found.passages]),
  );
  return items
    .map((item) => {
      const speaker = speakerLabel(item.participantInfo.identity);
      const text = item.text.trim();
      return {
        id: item.streamInfo.id,
        speaker,
        text,
        citations: speaker === "Agent" ? (byText.get(normalized(text)) ?? []) : [],
      };
    })
    .filter((line) => line.text.length > 0);
}
