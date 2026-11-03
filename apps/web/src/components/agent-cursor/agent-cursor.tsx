"use client";

import { useEffect, useState } from "react";

import { letterbox, type Size } from "@/lib/letterbox";
import type { HudPoint } from "@/lib/protocol";

export const IDLE_MS = 4000;

export type AgentCursorState = "pointing" | "thinking" | "about-to-click" | "clicking";

const SIZE = 22;
// The arrow path starts at (5, 2) in a 24 unit box. Shift it so the tip sits
// on the target.
const TIP = { x: (SIZE * 5) / 24, y: (SIZE * 2) / 24 };
const TAG = { x: SIZE * 0.62, y: SIZE * 0.72 };
// Past these fractions the tag would leave the picture, so it flips.
const FLIP = { x: 0.7, y: 0.8 };

// Adapted from the Figma Cursor snippet in Cursor Lab. See NOTICE.md.
function Arrow() {
  return (
    <svg
      width={SIZE}
      height={SIZE}
      viewBox="0 0 24 24"
      aria-hidden
      className="absolute overflow-visible drop-shadow-[0_1px_1.5px_rgb(0_0_0/0.35)]"
      style={{ left: -TIP.x, top: -TIP.y }}
    >
      <path
        d="M5 2l14 7-6 1.7L11 18z"
        fill="white"
        stroke="white"
        strokeWidth={6}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <path
        d="M5 2l14 7-6 1.7L11 18z"
        fill="var(--hui-color-background-accent-emphasis)"
        stroke="var(--hui-color-background-accent-emphasis)"
        strokeWidth={3.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ThinkingDots() {
  return (
    <span aria-hidden className="ml-1.5 inline-flex items-center gap-0.5">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="size-1 rounded-full bg-current motion-safe:animate-pulse"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  );
}

function cursorState(point: HudPoint | null, thinking: boolean): AgentCursorState {
  if (point?.kind === "about-to-click" || point?.kind === "clicking") {
    return point.kind;
  }
  return thinking ? "thinking" : "pointing";
}

function announcement(state: AgentCursorState, name: string, label: string): string {
  if (state === "about-to-click") {
    return `${name} is about to click ${label}`;
  }
  return state === "clicking" ? `${name} clicks ${label}` : `${name} points at ${label}`;
}

// A pulsing ring while a click waits for the user, one ripple when it happens.
function Ring({ state }: { state: AgentCursorState }) {
  if (state !== "about-to-click" && state !== "clicking") {
    return null;
  }
  return (
    <span
      data-testid="agent-cursor-ring"
      aria-hidden
      className={`absolute -top-3 -left-3 size-6 rounded-full border-2 border-[var(--hui-color-background-accent-emphasis)] ${state === "about-to-click" ? "motion-safe:animate-ping" : "motion-safe:[animation:ping_600ms_var(--motion-ease-out)_1_forwards]"}`}
    />
  );
}

// Hidden until the agent points. It glides to each new target inside the
// picture, names itself and the control, and fades out after IDLE_MS. A click
// that waits for the user's approval stays until the agent moves on.
export function AgentCursor({
  name,
  point,
  thinking,
  container,
  video,
}: {
  name: string;
  point: HudPoint | null;
  thinking: boolean;
  container: Size;
  video: Size;
}) {
  const [seen, setSeen] = useState<HudPoint | null>(null);
  const [idle, setIdle] = useState(true);
  // A new point wakes the cursor. React re-renders at once, before paint.
  if (point !== seen) {
    setSeen(point);
    setIdle(point === null);
  }
  const state = cursorState(point, thinking);
  const waiting = state === "about-to-click";
  useEffect(() => {
    if (idle || waiting) {
      return;
    }
    const timer = setTimeout(() => setIdle(true), IDLE_MS);
    return () => clearTimeout(timer);
  }, [idle, seen, waiting]);

  const frame = letterbox(container, video);
  const at = point ?? { x: 0.5, y: 0.5, label: "" };
  const flipX = at.x > FLIP.x;
  const flipY = at.y > FLIP.y;
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <span role="status" aria-label="Pointer" className="sr-only">
        {idle || point === null ? "" : announcement(state, name, point.label)}
      </span>
      <div
        data-testid="agent-cursor"
        data-state={state}
        aria-hidden
        className={`absolute top-0 left-0 will-change-transform motion-safe:[transition:transform_300ms_cubic-bezier(0.23,1,0.32,1),opacity_200ms_ease-out,visibility_200ms] motion-reduce:[transition:opacity_150ms_ease-out,visibility_150ms] ${idle ? "invisible opacity-0" : "visible opacity-100"}`}
        style={{
          transform: `translate3d(${frame.left + at.x * frame.width}px, ${frame.top + at.y * frame.height}px, 0)`,
        }}
      >
        <Ring key={`${state}-${at.x}-${at.y}`} state={state} />
        <Arrow />
        <p
          data-testid="agent-cursor-tag"
          className="absolute w-max max-w-48 rounded-lg bg-[var(--hui-color-background-accent-emphasis)] px-2 py-1 text-xs leading-4 text-[var(--hui-color-foreground-accent-emphasis)] shadow-[0_1px_2px_rgb(0_0_0/0.2),0_4px_12px_rgb(0_0_0/0.15)] [overflow-wrap:anywhere]"
          style={{
            ...(flipX ? { right: 6 } : { left: TAG.x }),
            ...(flipY ? { bottom: 10 } : { top: TAG.y }),
          }}
        >
          <span className="flex items-center font-medium">
            {name}
            {state === "thinking" ? <ThinkingDots /> : null}
          </span>
          <span className="block">{at.label}</span>
        </p>
      </div>
    </div>
  );
}
