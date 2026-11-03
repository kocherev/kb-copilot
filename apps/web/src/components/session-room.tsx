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
import { ScreenHud } from "@/components/screen-hud";
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
  onRestart,
}: {
  url: string;
  token: string;
  apiUrl: string;
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
      <SessionBody apiUrl={apiUrl} onRestart={onRestart} />
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

function ScreenStage({ point }: { point: HudPoint | null }) {
  const assistant = useVoiceAssistant();
  const tracks = useTracks([Track.Source.ScreenShare], { onlySubscribed: false });
  const shared = tracks.find((track) => track.publication);
  const { ref, size } = useElementSize();
  return (
    <section aria-label="Shared screen" className="flex min-w-0 flex-col gap-2">
      <div
        ref={ref}
        className="relative aspect-video w-full overflow-hidden rounded-md border border-border bg-muted"
      >
        {shared ? (
          <VideoTrack trackRef={shared} className="h-full w-full object-contain" />
        ) : (
          <p className="px-4 py-8 text-sm leading-6 text-muted-foreground">
            Share your screen so the agent can see it.
          </p>
        )}
        <ScreenHud
          thinking={assistant.state === "thinking"}
          point={point}
          container={size}
          video={shared?.publication?.dimensions ?? { width: 0, height: 0 }}
        />
      </div>
      <p className="text-pretty text-sm leading-6 text-muted-foreground">
        The highlight is drawn on this preview. It does not move your mouse.
      </p>
    </section>
  );
}

function SessionBody({ apiUrl, onRestart }: { apiUrl: string; onRestart: () => void }) {
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
      <ScreenStage point={point} />
      {proposals.map((proposal) => (
        <HandoffCard key={proposal.id} apiUrl={apiUrl} proposal={proposal} />
      ))}
      <TranscriptPanel lines={lines} />
    </>
  );
}
