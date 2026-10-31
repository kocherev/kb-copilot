import { errorDetail } from "@/lib/api";

export type SessionGrant = {
  url: string;
  token: string;
  room: string;
};

export type SessionLoad =
  | { status: "ready"; session: SessionGrant }
  | { status: "error"; message: string };

export type TranscriptLine = {
  id: string;
  speaker: string;
  text: string;
};

export const sessionPublish = {
  audio: true,
  video: false,
  screen: true,
} as const;

export function sessionFromResponse(status: number, body: unknown): SessionLoad {
  if (status === 404) {
    return { status: "error", message: "Product not found." };
  }
  if (status >= 200 && status < 300 && isSessionGrant(body)) {
    return { status: "ready", session: body };
  }
  return {
    status: "error",
    message: errorDetail(body, "Could not start the session."),
  };
}

export function isSessionGrant(body: unknown): body is SessionGrant {
  if (typeof body !== "object" || body === null) {
    return false;
  }
  const record = body as Record<string, unknown>;
  return (
    typeof record.url === "string" &&
    record.url.length > 0 &&
    typeof record.token === "string" &&
    record.token.length > 0 &&
    typeof record.room === "string" &&
    record.room.length > 0
  );
}

export function speakerLabel(identity: string): string {
  return identity === "user" ? "You" : "Agent";
}

export function transcriptLines(
  items: {
    text: string;
    participantInfo: { identity: string };
    streamInfo: { id: string };
  }[],
): TranscriptLine[] {
  return items
    .filter((item) => item.text.length > 0)
    .map((item) => ({
      id: item.streamInfo.id,
      speaker: speakerLabel(item.participantInfo.identity),
      text: item.text,
    }));
}
