import { errorDetail, type SessionGrant } from "@/lib/api/client";

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

export const HUD_TOPIC = "hud";

export type HudPoint = {
  x: number;
  y: number;
  label: string;
};

export type HudState = {
  thinking: boolean;
  point: HudPoint | null;
};

export const emptyHud: HudState = { thinking: false, point: null };

function unit(value: number): number {
  if (value < 0) {
    return 0;
  }
  if (value > 1) {
    return 1;
  }
  return value;
}

export function applyHudMessage(state: HudState, raw: string): HudState {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return state;
  }
  if (typeof parsed !== "object" || parsed === null) {
    return state;
  }
  const record = parsed as Record<string, unknown>;
  if (record.kind === "thinking" && typeof record.active === "boolean") {
    return { ...state, thinking: record.active };
  }
  if (
    record.kind === "point" &&
    typeof record.x === "number" &&
    Number.isFinite(record.x) &&
    typeof record.y === "number" &&
    Number.isFinite(record.y) &&
    typeof record.label === "string" &&
    record.label.trim().length > 0
  ) {
    return {
      ...state,
      point: {
        x: unit(record.x),
        y: unit(record.y),
        label: record.label.trim(),
      },
    };
  }
  return state;
}

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
export function speakerLabel(identity: string): string {
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
