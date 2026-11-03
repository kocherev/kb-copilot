"use client";

import {
  LiveKitRoom,
  RoomAudioRenderer,
  TrackToggle,
  VideoTrack,
  useConnectionState,
  useDataChannel,
  useRoomContext,
  useTracks,
  useTranscriptions,
  useVoiceAssistant,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { useEffect, useRef, useState } from "react";

import { HandoffCard } from "@/components/handoff-card";
import { AgentCursor } from "@/components/agent-cursor/agent-cursor";
import { ScreenGlow } from "@/components/screen-glow";
import { TranscriptPanel } from "@/components/transcript-panel";
import { Button } from "@/components/ui/button";
import {
  AGENT_ERROR_TOPIC,
  CITATIONS_TOPIC,
  ESCALATION_TOPIC,
  HUD_TOPIC,
  parseAgentError,
  parseCitations,
  parseEscalation,
  parseHudPoint,
  type Citations,
  type EscalationProposal,
  type HudPoint,
} from "@/lib/protocol";
import {
  connectionLabel,
  sessionPublish,
  transcriptLines,
} from "@/lib/session";

const decode = (payload: Uint8Array) => new TextDecoder().decode(payload);

export function SessionRoom({
  url,
  token,
  apiUrl,
  agentName,
  onRestart,
}: {
  url: string;
  token: string;
  apiUrl: string;
  agentName: string;
  onRestart: () => void;
}) {
  const [roomError, setRoomError] = useState<string | null>(null);
  return (
    <LiveKitRoom
      serverUrl={url}
      token={token}
      connect
      audio={sessionPublish.audio}
      video={sessionPublish.video}
      screen={sessionPublish.screen}
      onError={(error) => setRoomError(error.message)}
      className="flex min-w-0 flex-col gap-6"
    >
      <RoomAudioRenderer />
      {roomError ? (
        <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
          {roomError}
        </p>
      ) : null}
      <SessionBody apiUrl={apiUrl} agentName={agentName} onRestart={onRestart} />
    </LiveKitRoom>
  );
}

function useElementSize() {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const element = ref.current;
    if (!element) {
      return;
    }
    const watch = new ResizeObserver(([entry]) => {
      if (entry) {
        setSize({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    watch.observe(element);
    return () => watch.disconnect();
  }, []);
  return { ref, size };
}

function presence(name: string, watching: boolean, agentState: string): string {
  if (!watching) {
    return "";
  }
  if (agentState === "thinking") {
    return `${name} is thinking`;
  }
  return agentState === "speaking" ? `${name} is speaking` : `${name} is watching your screen`;
}

function ScreenStage({ point, agentName }: { point: HudPoint | null; agentName: string }) {
  const assistant = useVoiceAssistant();
  const connection = useConnectionState();
  const tracks = useTracks([Track.Source.ScreenShare], { onlySubscribed: false });
  const shared = tracks.find((track) => track.publication);
  const { ref, size } = useElementSize();
  const watching =
    connection === "connected" && shared !== undefined && assistant.agent !== undefined;
  return (
    <section aria-label="Shared screen" className="flex min-w-0 flex-col gap-2">
      <ScreenGlow watching={watching} agentState={assistant.state}>
        <div
          ref={ref}
          className="relative aspect-video w-full overflow-hidden rounded-md border border-border bg-muted"
        >
          {shared ? (
            <VideoTrack trackRef={shared} className="h-full w-full object-contain" />
          ) : (
            <p className="px-4 py-8 text-sm leading-6 text-muted-foreground">
              Share your screen so {agentName} can see it.
            </p>
          )}
          <AgentCursor
            name={agentName}
            point={point}
            thinking={assistant.state === "thinking"}
            container={size}
            video={shared?.publication?.dimensions ?? { width: 0, height: 0 }}
          />
        </div>
      </ScreenGlow>
      <p role="status" aria-label="Agent" className="min-h-6 text-sm leading-6 text-foreground">
        {presence(agentName, watching, assistant.state)}
      </p>
      <p className="text-pretty text-sm leading-6 text-muted-foreground">
        {agentName}&rsquo;s pointer is drawn on this preview. It does not move your mouse.
      </p>
    </section>
  );
}

function SessionBody({
  apiUrl,
  agentName,
  onRestart,
}: {
  apiUrl: string;
  agentName: string;
  onRestart: () => void;
}) {
  const room = useRoomContext();
  const state = useConnectionState();
  const [point, setPoint] = useState<HudPoint | null>(null);
  const [citations, setCitations] = useState<Citations[]>([]);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [proposals, setProposals] = useState<EscalationProposal[]>([]);
  useDataChannel(HUD_TOPIC, (message) => {
    const next = parseHudPoint(decode(message.payload));
    if (next) {
      setPoint(next);
    }
  });
  useDataChannel(CITATIONS_TOPIC, (message) => {
    const found = parseCitations(decode(message.payload));
    if (found) {
      setCitations((current) => [
        ...current.filter((item) => item.messageId !== found.messageId),
        found,
      ]);
    }
  });
  useDataChannel(AGENT_ERROR_TOPIC, (message) => {
    setAgentError(parseAgentError(decode(message.payload)));
  });
  useDataChannel(ESCALATION_TOPIC, (message) => {
    const proposal = parseEscalation(decode(message.payload));
    if (proposal) {
      setProposals((current) =>
        current.some((item) => item.id === proposal.id) ? current : [...current, proposal],
      );
    }
  });
  const lines = transcriptLines(useTranscriptions(), citations);
  const ended = state === "disconnected";
  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <p role="status" aria-label="Connection" className="text-sm text-muted-foreground">
          {connectionLabel(state)}
        </p>
        {ended ? (
          <Button type="button" onClick={onRestart}>
            New session
          </Button>
        ) : (
          <Button type="button" onClick={() => void room.disconnect()}>
            End session
          </Button>
        )}
      </div>
      {agentError ? (
        <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
          {agentError}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-3">
        <TrackToggle source={Track.Source.Microphone} aria-label="Microphone" />
        <TrackToggle source={Track.Source.ScreenShare} aria-label="Screen share" />
      </div>
      <ScreenStage point={point} agentName={agentName} />
      {proposals.map((proposal) => (
        <HandoffCard key={proposal.id} apiUrl={apiUrl} proposal={proposal} />
      ))}
      <TranscriptPanel lines={lines} />
    </>
  );
}
