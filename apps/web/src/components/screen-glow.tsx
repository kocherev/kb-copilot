"use client";

import { BorderBeam } from "border-beam";
import type { ReactNode } from "react";

import { usePageTheme, useReducedMotion } from "@/lib/page-environment";

// Calm and blue while the agent listens, livelier while it works or talks.
const levels = {
  listening: { colorVariant: "ocean", strength: 0.6, duration: 3.2 },
  thinking: { colorVariant: "colorful", strength: 0.85, duration: 1.6 },
  speaking: { colorVariant: "colorful", strength: 1, duration: 2.2 },
} as const;

// Border Beam's light preset is too pale to read on a white page.
const tuning = {
  light: { brightness: 1.7, saturation: 2.4 },
  dark: {},
} as const;

export function glowLevel(agentState: string): keyof typeof levels {
  return agentState === "thinking" || agentState === "speaking"
    ? agentState
    : "listening";
}

// The glow says the agent is watching the shared screen. It is on only while
// the room is connected, the screen is shared, and the agent is in the room.
export function ScreenGlow({
  watching,
  agentState,
  children,
}: {
  watching: boolean;
  agentState: string;
  children: ReactNode;
}) {
  const theme = usePageTheme();
  const reducedMotion = useReducedMotion();
  if (reducedMotion) {
    // Border Beam turns its own animation off for this setting and then shows
    // nothing, so a still ring carries the same message.
    return (
      <div
        data-glow={watching ? "static" : "off"}
        className={`rounded-md ${watching ? "ring-2 ring-[color-mix(in_oklch,var(--hui-color-border-accent-emphasis)_45%,transparent)]" : ""}`}
      >
        {children}
      </div>
    );
  }
  return (
    <BorderBeam
      data-glow={watching ? "animated" : "off"}
      active={watching}
      size="pulse-outside"
      glowSize={1.4}
      theme={theme}
      {...tuning[theme]}
      {...levels[glowLevel(agentState)]}
    >
      {children}
    </BorderBeam>
  );
}
