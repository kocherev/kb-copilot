// Mirrors services/agent/src/kb_agent/protocol.py.
// services/agent/tests/test_protocol.py fails when the names drift.
export const AGENT_NAME = "kb-support";
export const HUD_TOPIC = "hud";
export const CITATIONS_TOPIC = "citations";
export const AGENT_ERROR_TOPIC = "agent-error";
export const ESCALATION_TOPIC = "escalation";
export const COMPUTER_TOPIC = "computer";
export const COMPUTER_DECISION_TOPIC = "computer-decision";

// point is a highlight. about-to-click comes from a proposal waiting for the
// user. clicking means the agent is clicking there on the user's computer.
export type CursorKind = "point" | "about-to-click" | "clicking";

export type HudPoint = { kind: CursorKind; x: number; y: number; label: string };

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

export type EscalationProposal = { id: string; title: string; body: string };

export type ActionProposal = {
  id: string;
  task: string;
  description: string;
  target: { x: number; y: number } | null;
  needsApproval: boolean;
  warning: string;
};

export type ComputerMessage =
  | { kind: "proposal"; proposal: ActionProposal }
  | { kind: "ended"; task: string };

export type Decision = "once" | "task" | "stop";

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
  const kind = body?.kind;
  if ((kind !== "point" && kind !== "clicking") || typeof body?.label !== "string") {
    return null;
  }
  const x = fraction(body.x);
  const y = fraction(body.y);
  const label = body.label.trim();
  return x === null || y === null || label === "" ? null : { kind, x, y, label };
}

export function parseComputerMessage(raw: string): ComputerMessage | null {
  const body = record(raw);
  if (typeof body?.task !== "string" || body.task === "") {
    return null;
  }
  if (body.kind === "ended") {
    return { kind: "ended", task: body.task };
  }
  if (
    body.kind !== "proposal" ||
    typeof body.id !== "string" ||
    body.id === "" ||
    typeof body.description !== "string" ||
    body.description.trim() === "" ||
    typeof body.needs_approval !== "boolean"
  ) {
    return null;
  }
  const x = fraction(body.x);
  const y = fraction(body.y);
  return {
    kind: "proposal",
    proposal: {
      id: body.id,
      task: body.task,
      description: body.description.trim(),
      target: x === null || y === null ? null : { x, y },
      needsApproval: body.needs_approval,
      warning: typeof body.warning === "string" ? body.warning.trim() : "",
    },
  };
}

export function decisionMessage(id: string, decision: Decision): Uint8Array {
  return new TextEncoder().encode(JSON.stringify({ id, decision }));
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

export function parseEscalation(raw: string): EscalationProposal | null {
  const body = record(raw);
  if (
    typeof body?.id !== "string" ||
    typeof body.title !== "string" ||
    typeof body.body !== "string" ||
    body.id === "" ||
    body.title.trim() === ""
  ) {
    return null;
  }
  return { id: body.id, title: body.title.trim(), body: body.body.trim() };
}
