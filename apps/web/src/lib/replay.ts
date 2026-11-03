import { errorDetail, type Replay, type SessionSummary, type Turn } from "@/lib/api/client";

export type ReplayLoad =
  | { status: "ready"; replay: Replay }
  | { status: "missing" }
  | { status: "error"; message: string };

export function replayLoad(
  status: number,
  replay: Replay | undefined,
  error: unknown,
): ReplayLoad {
  // A session id that is not a UUID is a 422, and is as missing as an unknown one.
  if (status === 404 || status === 422) {
    return { status: "missing" };
  }
  if (replay === undefined) {
    return { status: "error", message: errorDetail(error, "Could not load the session.") };
  }
  return { status: "ready", replay };
}

export type Stage = { key: string; label: string; ms: number };

// The order a stage happens in, for each side of the conversation. "search" is
// not a measured key: it is the time the turn's searches took.
const STAGES: Record<Turn["role"], readonly (readonly [key: string, label: string])[]> = {
  user: [
    ["end_of_turn_delay_ms", "End of turn"],
    ["transcription_delay_ms", "Transcript"],
  ],
  assistant: [
    ["search", "Search"],
    ["llm_ttft_ms", "Model first token"],
    ["tts_ttfb_ms", "First audio"],
  ],
};

export const stageLabels: readonly (readonly [key: string, label: string])[] = [
  ...STAGES.user,
  ...STAGES.assistant,
];

export function stagesOf(turn: Turn): Stage[] {
  const searched = turn.searches.reduce((sum, search) => sum + search.duration_ms, 0);
  const measured: Record<string, number | undefined> = { ...turn.latency, search: searched || undefined };
  return STAGES[turn.role].flatMap(([key, label]) => {
    const ms = measured[key];
    return ms === undefined ? [] : [{ key, label, ms }];
  });
}

// The agent's own end-to-end figure when it measured one, else the stages added up.
export function totalMs(turn: Turn, stages: Stage[]): number {
  return turn.latency.e2e_latency_ms ?? stages.reduce((sum, stage) => sum + stage.ms, 0);
}

export function formatMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;
}

function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function formatDuration(from: string, to: string): string {
  return clock(Math.max(0, Math.round((Date.parse(to) - Date.parse(from)) / 1000)));
}

// UTC on purpose: the server renders the replay, and its zone is not the reader's.
export function formatStart(iso: string): string {
  const text = new Date(iso).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  });
  return `${text} UTC`;
}

export function offsetLabel(from: string, at: string): string {
  return `+${formatDuration(from, at)}`;
}

export function countLabel(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

export function summaryLine(session: SessionSummary): string {
  return [
    ...(session.ended_at ? [formatDuration(session.created_at, session.ended_at)] : []),
    countLabel(session.turn_count, "turn"),
    countLabel(session.action_count, "action"),
    countLabel(session.handoff_count, "handoff"),
  ].join(", ");
}

const EVENT_LABELS: Record<string, string> = {
  proposed: "Proposed",
  approved: "Allowed",
  denied: "Denied",
  timed_out: "No answer",
  performed: "Done",
  failed: "Failed",
  ended: "Task ended",
};

export function eventLabel(event: string): string {
  return EVENT_LABELS[event] ?? event;
}
