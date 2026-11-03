// Mirrors services/agent/src/kb_agent/protocol.py.
// services/agent/tests/test_protocol.py fails when the names drift.
export const AGENT_NAME = "kb-support";
export const HUD_TOPIC = "hud";
export const CITATIONS_TOPIC = "citations";
export const AGENT_ERROR_TOPIC = "agent-error";

export type HudPoint = { x: number; y: number; label: string };

export type CitedPassage = {
  id: string;
  title: string;
  source: string;
  anchor: string;
  snippet: string;
};

export type Citations = {
  messageId: string;
  text: string;
  passages: CitedPassage[];
};

function record(raw: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function fraction(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  return Math.min(1, Math.max(0, value));
}

export function parseHudPoint(raw: string): HudPoint | null {
  const body = record(raw);
  if (body?.kind !== "point" || typeof body.label !== "string") {
    return null;
  }
  const x = fraction(body.x);
  const y = fraction(body.y);
  const label = body.label.trim();
  return x === null || y === null || label === "" ? null : { x, y, label };
}

function parsePassage(value: unknown): CitedPassage | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const { id, title, source, anchor, snippet } = value as Record<string, unknown>;
  if (
    typeof id !== "string" ||
    typeof title !== "string" ||
    typeof source !== "string" ||
    typeof anchor !== "string" ||
    typeof snippet !== "string"
  ) {
    return null;
  }
  return { id, title, source, anchor, snippet };
}

export function parseCitations(raw: string): Citations | null {
  const body = record(raw);
  if (
    typeof body?.message_id !== "string" ||
    typeof body.text !== "string" ||
    !Array.isArray(body.passages)
  ) {
    return null;
  }
  const passages = body.passages.map(parsePassage);
  if (passages.length === 0 || passages.includes(null)) {
    return null;
  }
  return {
    messageId: body.message_id,
    text: body.text,
    passages: passages as CitedPassage[],
  };
}

export function parseAgentError(raw: string): string | null {
  const message = record(raw)?.message;
  return typeof message === "string" && message.trim() !== "" ? message.trim() : null;
}
