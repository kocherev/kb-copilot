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
  sources: string[];
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

function splitAnswer(text: string): { text: string; sources: string[] } {
  const sources: string[] = [];
  const body: string[] = [];
  for (const line of text.split("\n")) {
    const match = /^Source:\s+(\S.*)$/.exec(line.trim());
    const source = match?.[1]?.trim();
    if (source) {
      if (!sources.includes(source)) {
        sources.push(source);
      }
      continue;
    }
    body.push(line);
  }
  return { text: body.join("\n").trim(), sources };
}

export function transcriptLines(
  items: {
    text: string;
    participantInfo: { identity: string };
    streamInfo: { id: string };
  }[],
): TranscriptLine[] {
  return items
    .map((item) => {
      const answer = splitAnswer(item.text);
      return {
        id: item.streamInfo.id,
        speaker: speakerLabel(item.participantInfo.identity),
        text: answer.text,
        sources: answer.sources,
      };
    })
    .filter((line) => line.text.length > 0 || line.sources.length > 0);
}
