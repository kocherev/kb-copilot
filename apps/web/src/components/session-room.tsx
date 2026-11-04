"use client";

import {
  LiveKitRoom,
  RoomAudioRenderer,
  VideoTrack,
  useConnectionState,
  useDataChannel,
  useRemoteParticipants,
  useRoomContext,
  useTrackToggle,
  useTracks,
  useTranscriptions,
  useVoiceAssistant,
  type TrackReference,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import {
  AudioLines,
  Ellipsis,
  Eye,
  Hourglass,
  Mic,
  MicOff,
  MonitorOff,
  MonitorUp,
  PhoneOff,
  PictureInPicture2,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import {
  startTransition,
  useEffect,
  useRef,
  useState,
  ViewTransition,
  type RefObject,
} from "react";

import { AgentCursor } from "@/components/agent-cursor/agent-cursor";
import { ApprovalTray } from "@/components/approval-tray";
import { ConnectMac } from "@/components/connect-mac";
import { HandoffCard } from "@/components/handoff-card";
import { PresenceWindow, usePresenceWindow } from "@/components/presence-window";
import { ScreenGlow } from "@/components/screen-glow";
import { TranscriptPanel } from "@/components/transcript-panel";
import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/inline-error";
import { Spinner } from "@/components/ui/spinner";
import type { Size } from "@/lib/letterbox";
import {
  AGENT_ERROR_TOPIC,
  CITATIONS_TOPIC,
  COMPUTER_DECISION_TOPIC,
  COMPUTER_TOPIC,
  ESCALATION_TOPIC,
  HUD_TOPIC,
  KB_PHASE_ATTRIBUTE,
  decisionMessage,
  parseAgentError,
  parseCitations,
  parseComputerMessage,
  parseEscalation,
  parseHudPoint,
  type ActionProposal,
  type Citations,
  type Decision,
  type EscalationProposal,
  type HudPoint,
} from "@/lib/protocol";
import {
  connectionLabel,
  roomPhase,
  sessionPublish,
  transcriptLines,
  type RoomPhase,
} from "@/lib/session";

const decode = (payload: Uint8Array) => new TextDecoder().decode(payload);

export function SessionRoom({
  url,
  token,
  room,
  apiUrl,
  agentName,
  onRestart,
}: {
  url: string;
  token: string;
  room: string;
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
      className="flex min-w-0 flex-col gap-4"
    >
      <RoomAudioRenderer />
      {roomError ? (
        <InlineError onRetry={onRestart}>Could not join the room: {roomError}</InlineError>
      ) : null}
      <SessionBody
        apiUrl={apiUrl}
        roomName={room}
        agentName={agentName}
        onRestart={onRestart}
      />
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

type Presence = { text: string; Icon: LucideIcon; live: boolean };

// The floating window already shows the name, so its status line drops it.
function withoutName(text: string, name: string): string {
  const prefix = `${name} is `;
  if (!text.startsWith(prefix)) {
    return text;
  }
  const rest = text.slice(prefix.length);
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

function presence(phase: RoomPhase, name: string, agentState: string): Presence {
  switch (phase) {
    case "connecting":
      return { text: "Connecting", Icon: Hourglass, live: false };
    case "joining":
      return { text: `${name} is joining`, Icon: UserRound, live: false };
    case "share":
      return { text: `Share your screen so ${name} can see it`, Icon: MonitorUp, live: false };
    case "share-stopped":
      return {
        text: `Screen sharing stopped, so ${name} can’t see your screen`,
        Icon: MonitorOff,
        live: false,
      };
    case "left":
      return { text: `${name} left the call`, Icon: PhoneOff, live: false };
    case "live":
      if (agentState === "thinking") {
        return { text: `${name} is thinking`, Icon: Ellipsis, live: true };
      }
      if (agentState === "speaking") {
        return { text: `${name} is speaking`, Icon: AudioLines, live: true };
      }
      return { text: `${name} is watching your screen`, Icon: Eye, live: true };
    default:
      return { text: "", Icon: UserRound, live: false };
  }
}

// Shawn's state is the first thing to read in the room: an icon that changes
// with each state, and a sentence for screen readers and everyone else.
function PresenceLine({ presence: { text, Icon, live }, speaking }: { presence: Presence; speaking: boolean }) {
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      {text === "" ? null : (
        <span
          aria-hidden
          className={`grid size-9 shrink-0 place-items-center rounded-full transition-[background-color,color] duration-200 ease-out ${speaking ? "bg-primary text-primary-foreground" : live ? "bg-primary-soft text-primary-soft-foreground" : "bg-surface-sunken text-muted-foreground"}`}
        >
          <Icon
            key={text}
            className="size-4 animate-enter [--motion-y:3px] motion-reduce:[--motion-y:0px]"
          />
        </span>
      )}
      <p role="status" aria-label="Agent" className="min-w-0 text-sm font-medium text-foreground">
        {text}
      </p>
    </div>
  );
}

const connectionTones: Record<string, string> = {
  connected: "bg-success-soft text-success",
  reconnecting: "bg-warning-soft text-warning",
  signalReconnecting: "bg-warning-soft text-warning",
};

function ConnectionBadge({ state }: { state: string }) {
  const waiting = state !== "connected" && state !== "disconnected";
  return (
    <p
      role="status"
      aria-label="Connection"
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-meta font-medium ${connectionTones[state] ?? "bg-surface-sunken text-muted-foreground"}`}
    >
      {waiting ? (
        <Spinner className="size-3.5" />
      ) : (
        <span aria-hidden className="size-1.5 rounded-full bg-current" />
      )}
      {connectionLabel(state)}
    </p>
  );
}

function SharePrompt({
  large,
  note,
  onShared,
}: {
  large: boolean;
  note: string;
  onShared: () => void;
}) {
  const { toggle, pending } = useTrackToggle({ source: Track.Source.ScreenShare });
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
      <Button
        type="button"
        size={large ? "xl" : "default"}
        disabled={pending}
        onClick={() => void toggle(true).then(onShared)}
      >
        <MonitorUp aria-hidden />
        Share your screen
      </Button>
      <p className="max-w-[40ch] text-meta text-pretty text-muted-foreground">{note}</p>
    </div>
  );
}

function StageWaiting({ children }: { children: string }) {
  return (
    <div className="flex h-full items-center justify-center gap-2 p-6 text-sm text-muted-foreground">
      <Spinner />
      {children}
    </div>
  );
}

function StageEnd({ title, onRestart }: { title: string; onRestart: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
      <span className="grid size-10 place-items-center rounded-full bg-primary-soft text-primary-soft-foreground max-sm:hidden">
        <PhoneOff aria-hidden className="size-5" />
      </span>
      <p className="font-display text-xl/tight text-foreground">{title}</p>
      <p className="max-w-[40ch] text-meta text-pretty text-muted-foreground">
        The transcript stays on this page until you leave.
      </p>
      <Button type="button" onClick={onRestart}>
        New session
      </Button>
    </div>
  );
}

function StagePlaceholder({
  phase,
  agentName,
  onRestart,
  onShared,
}: {
  phase: RoomPhase;
  agentName: string;
  onRestart: () => void;
  onShared: () => void;
}) {
  switch (phase) {
    case "ended":
      return <StageEnd title="Session ended" onRestart={onRestart} />;
    case "left":
      return <StageEnd title={`${agentName} left the call`} onRestart={onRestart} />;
    case "share":
      return (
        <SharePrompt
          large
          note={`${agentName} starts talking once your screen is shared.`}
          onShared={onShared}
        />
      );
    case "share-stopped":
      return (
        <SharePrompt
          large={false}
          note={`${agentName} can’t see your screen until you share it again.`}
          onShared={onShared}
        />
      );
    case "joining":
      return <StageWaiting>{`${agentName} is joining…`}</StageWaiting>;
    case "reconnecting":
      return <StageWaiting>Reconnecting…</StageWaiting>;
    default:
      return <StageWaiting>Connecting…</StageWaiting>;
  }
}

function ScreenStage({
  point,
  agentName,
  phase,
  agentState,
  shared,
  video,
  videoRef,
  onRestart,
  onShared,
}: {
  point: HudPoint | null;
  agentName: string;
  phase: RoomPhase;
  agentState: string;
  shared: TrackReference | undefined;
  video: Size;
  videoRef: RefObject<HTMLVideoElement | null>;
  onRestart: () => void;
  onShared: () => void;
}) {
  const { ref, size } = useElementSize();
  const showVideo = shared !== undefined && (phase === "live" || phase === "reconnecting");
  return (
    <section aria-label="Shared screen" className="flex min-w-0 flex-col gap-2">
      <ScreenGlow watching={phase === "live"} agentState={agentState}>
        <div
          ref={ref}
          className="relative aspect-video w-full overflow-hidden rounded-panel border border-transparent bg-surface-sunken shadow-ring"
        >
          {showVideo ? (
            <VideoTrack
              ref={videoRef}
              trackRef={shared}
              className={`h-full w-full object-contain transition-opacity duration-200 ease-out ${phase === "reconnecting" ? "opacity-50" : ""}`}
            />
          ) : (
            <StagePlaceholder
              phase={phase}
              agentName={agentName}
              onRestart={onRestart}
              onShared={onShared}
            />
          )}
          <AgentCursor
            name={agentName}
            point={point}
            thinking={agentState === "thinking"}
            container={size}
            video={video}
          />
        </div>
      </ScreenGlow>
      {showVideo ? (
        <p className="text-meta text-pretty text-muted-foreground">
          {agentName}&rsquo;s pointer is drawn on this preview. It moves your mouse only for a
          step you allow.
        </p>
      ) : null}
    </section>
  );
}

const toggleBase =
  "relative grid size-11 place-items-center rounded-full outline-none transition-[scale,background-color,color] duration-150 ease-out focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-50 motion-safe:enabled:active:scale-[0.96]";

function TrackToggleButton({
  source,
  label,
  on: OnIcon,
  off: OffIcon,
  onClass,
  offClass,
  onDeviceError,
}: {
  source: Track.Source.Microphone | Track.Source.ScreenShare;
  label: string;
  on: LucideIcon;
  off: LucideIcon;
  onClass: string;
  offClass: string;
  onDeviceError: (error: Error) => void;
}) {
  const { enabled, pending, toggle } = useTrackToggle({ source, onDeviceError });
  const Icon = enabled ? OnIcon : OffIcon;
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={enabled}
      title={label}
      disabled={pending}
      onClick={() => void toggle()}
      className={`${toggleBase} ${enabled ? onClass : offClass}`}
    >
      <Icon aria-hidden className="size-5" />
    </button>
  );
}

// Docked to the bottom of the screen on phones, under the stage on desktop.
function ControlBar({
  agentName,
  presenceWindow,
  onEnd,
  onDeviceError,
}: {
  agentName: string;
  presenceWindow: { supported: boolean; open: boolean; toggle: () => void };
  onEnd: () => void;
  onDeviceError: (error: Error) => void;
}) {
  const onTop = `Keep ${agentName} on top`;
  return (
    <div className="fixed inset-x-0 bottom-0 z-(--z-overlay) border-t border-border bg-background/90 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur-md lg:static lg:border-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none">
      <div
        role="group"
        aria-label="Session controls"
        className="mx-auto flex w-fit items-center gap-1.5 rounded-full border border-transparent bg-surface p-1.5 shadow-soft"
      >
        <TrackToggleButton
          source={Track.Source.Microphone}
          label="Microphone"
          on={Mic}
          off={MicOff}
          onClass="text-foreground hover:bg-surface-hover"
          offClass="bg-destructive-soft text-destructive"
          onDeviceError={onDeviceError}
        />
        <TrackToggleButton
          source={Track.Source.ScreenShare}
          label="Screen share"
          on={MonitorUp}
          off={MonitorOff}
          onClass="bg-primary-soft text-primary-soft-foreground"
          offClass="text-muted-foreground hover:bg-surface-hover"
          onDeviceError={onDeviceError}
        />
        {presenceWindow.supported ? (
          <button
            type="button"
            aria-label={onTop}
            aria-pressed={presenceWindow.open}
            title={onTop}
            onClick={presenceWindow.toggle}
            className={`${toggleBase} ${presenceWindow.open ? "bg-primary-soft text-primary-soft-foreground" : "text-muted-foreground hover:bg-surface-hover"}`}
          >
            <PictureInPicture2 aria-hidden className="size-5" />
          </button>
        ) : null}
        <span aria-hidden className="mx-1 h-6 w-px bg-border" />
        <Button
          type="button"
          variant="destructive"
          className="h-11 rounded-full px-4"
          onClick={onEnd}
        >
          <PhoneOff aria-hidden className="size-4" />
          <span className="max-sm:sr-only">End session</span>
        </Button>
      </div>
    </div>
  );
}

function deviceMessage(error: Error): string {
  return error.name === "NotAllowedError"
    ? "Your browser blocked access. Allow the microphone and screen for this site, then try the button again."
    : `That device did not start: ${error.message}`;
}

function SessionBody({
  apiUrl,
  roomName,
  agentName,
  onRestart,
}: {
  apiUrl: string;
  roomName: string;
  agentName: string;
  onRestart: () => void;
}) {
  const room = useRoomContext();
  const state = useConnectionState();
  const assistant = useVoiceAssistant();
  const shared = useTracks([Track.Source.ScreenShare], { onlySubscribed: false }).find(
    (track) => track.publication,
  );
  const helperConnected = useRemoteParticipants().some((participant) =>
    participant.identity.startsWith("desktop:"),
  );
  const [point, setPoint] = useState<HudPoint | null>(null);
  const [proposal, setProposal] = useState<ActionProposal | null>(null);
  const [citations, setCitations] = useState<Citations[]>([]);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [deviceError, setDeviceError] = useState<string | null>(null);
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
  const decisions = useDataChannel(COMPUTER_DECISION_TOPIC);
  useDataChannel(COMPUTER_TOPIC, (message) => {
    const update = parseComputerMessage(decode(message.payload));
    // In a transition, so the tray's <ViewTransition> animates in and out.
    startTransition(() => {
      if (update?.kind === "ended") {
        setProposal(null);
        setPoint((current) => (current?.kind === "about-to-click" ? null : current));
      } else if (update) {
        const { target, description } = update.proposal;
        setProposal(update.proposal);
        if (target) {
          setPoint({ kind: "about-to-click", ...target, label: description });
        }
      }
    });
  });
  function decide(decision: Decision) {
    if (!proposal) {
      return;
    }
    void decisions.send(decisionMessage(proposal.id, decision), { reliable: true });
    startTransition(() => {
      setProposal(null);
      if (decision === "stop") {
        setPoint(null);
      }
    });
  }
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
  const phase = roomPhase({
    state,
    agentPresent: assistant.agent !== undefined,
    agentPhase: assistant.agentAttributes?.[KB_PHASE_ATTRIBUTE],
    sharing: shared !== undefined,
    agentFailed: agentError !== null,
  });
  const line = presence(phase, agentName, assistant.state);
  const video = shared?.publication?.dimensions ?? { width: 0, height: 0 };
  const videoRef = useRef<HTMLVideoElement>(null);
  const presenceWindow = usePresenceWindow(!ended, agentName);
  // Opening needs the user's click. After the screen picker that click may
  // have expired, and then the control bar button stays as the way in.
  const openPresenceWindow = () => void presenceWindow.open().catch(() => {});
  const endSession = () => void room.disconnect();
  return (
    <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)] lg:items-start">
      <div className="flex min-w-0 flex-col gap-4">
        <div className="flex min-w-0 items-center justify-between gap-3">
          <PresenceLine
            presence={line}
            speaking={phase === "live" && assistant.state === "speaking"}
          />
          {phase === "connecting" ? null : <ConnectionBadge state={state} />}
        </div>
        {agentError ? <InlineError>{agentError}</InlineError> : null}
        {deviceError ? <InlineError>{deviceError}</InlineError> : null}
        <ScreenStage
          point={point}
          agentName={agentName}
          phase={phase}
          agentState={assistant.state}
          shared={shared}
          video={video}
          videoRef={videoRef}
          onRestart={onRestart}
          onShared={openPresenceWindow}
        />
        {proposal ? (
          <ViewTransition enter="vt-tray" exit="vt-tray" default="none">
            <ApprovalTray agentName={agentName} proposal={proposal} onDecide={decide} />
          </ViewTransition>
        ) : null}
        {ended ? null : (
          <ControlBar
            agentName={agentName}
            presenceWindow={{
              supported: presenceWindow.supported,
              open: presenceWindow.target !== null,
              toggle: presenceWindow.target ? presenceWindow.close : openPresenceWindow,
            }}
            onEnd={endSession}
            onDeviceError={(error) => setDeviceError(deviceMessage(error))}
          />
        )}
        {presenceWindow.target ? (
          <PresenceWindow
            target={presenceWindow.target}
            agentName={agentName}
            status={withoutName(line.text, agentName) || connectionLabel(state)}
            live={phase === "live"}
            agentState={assistant.state}
            point={point}
            video={video}
            source={videoRef}
            controls={
              <>
                <TrackToggleButton
                  source={Track.Source.Microphone}
                  label="Microphone"
                  on={Mic}
                  off={MicOff}
                  onClass="text-foreground hover:bg-surface-hover"
                  offClass="bg-destructive-soft text-destructive"
                  onDeviceError={(error) => setDeviceError(deviceMessage(error))}
                />
                <button
                  type="button"
                  aria-label="End session"
                  title="End session"
                  onClick={endSession}
                  className={`${toggleBase} bg-[color-mix(in_oklch,var(--hui-color-background-danger-emphasis)_90%,black)] text-[var(--hui-color-foreground-danger-emphasis)]`}
                >
                  <PhoneOff aria-hidden className="size-5" />
                </button>
              </>
            }
          />
        ) : null}
      </div>
      <aside
        aria-label="Session details"
        className="flex min-w-0 flex-col gap-4 lg:sticky lg:top-[4.5rem] lg:max-h-[calc(100dvh-10rem)]"
      >
        {proposals.map((proposal) => (
          <HandoffCard key={proposal.id} apiUrl={apiUrl} agentName={agentName} proposal={proposal} />
        ))}
        {ended ? null : (
          <ConnectMac
            apiUrl={apiUrl}
            room={roomName}
            agentName={agentName}
            connected={helperConnected}
          />
        )}
        <TranscriptPanel lines={lines} agentName={agentName} />
      </aside>
    </div>
  );
}
