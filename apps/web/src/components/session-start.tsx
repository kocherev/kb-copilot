"use client";

import {
  LiveKitRoom,
  RoomAudioRenderer,
  TrackToggle,
  VideoTrack,
  useConnectionState,
  useDataChannel,
  useTracks,
  useTranscriptions,
  useVoiceAssistant,
} from "@livekit/components-react";
import { ConnectionState, Track } from "livekit-client";
import Link from "next/link";
import { useState } from "react";

import { ScreenHud } from "@/components/screen-hud";
import { TranscriptPanel } from "@/components/transcript-panel";
import { Button } from "@/components/ui/button";
import { apiPath, readJson } from "@/lib/api";
import {
  HUD_TOPIC,
  applyHudMessage,
  emptyHud,
  sessionFromResponse,
  sessionPublish,
  transcriptLines,
  type HudState,
  type SessionGrant,
} from "@/lib/session";

const linkClass =
  "text-sm underline underline-offset-4 focus-visible:[outline:var(--hui-focus-ring)] focus-visible:outline-offset-[var(--hui-focus-ring-offset-accent)]";

export function SessionStart({
  apiUrl,
  productId,
  productName,
}: {
  apiUrl: string;
  productId: string;
  productName: string;
}) {
  const [session, setSession] = useState<SessionGrant | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function start() {
    setPending(true);
    setError(null);
    try {
      const response = await fetch(apiPath(apiUrl, "/sessions"), {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ product_id: productId }),
      });
      const loaded = sessionFromResponse(response.status, await readJson(response));
      if (loaded.status === "error") {
        setError(loaded.message);
        return;
      }
      setSession(loaded.session);
    } catch {
      setError("Could not start the session.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main
      className={`mx-auto flex min-h-dvh w-full min-w-0 flex-col gap-8 px-6 py-16 ${session ? "max-w-3xl" : "max-w-lg"}`}
    >
      <Link className={linkClass} href={`/products/${productId}`}>
        Product
      </Link>
      <h1 className="text-balance text-2xl font-medium tracking-tight text-foreground [overflow-wrap:anywhere]">
        {productName}
      </h1>
      {session ? (
        <SessionRoom url={session.url} token={session.token} />
      ) : (
        <>
          <p className="text-pretty text-sm leading-6 text-muted-foreground">
            Join with your microphone and share your screen. The agent answers
            by voice.
          </p>
          {error ? (
            <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
              {error}
            </p>
          ) : null}
          <Button type="button" disabled={pending} onClick={() => void start()}>
            Start session
          </Button>
        </>
      )}
    </main>
  );
}

export function SessionRoom({ url, token }: { url: string; token: string }) {
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
      <SessionBody />
    </LiveKitRoom>
  );
}

function ScreenStage() {
  const [hud, setHud] = useState<HudState>(emptyHud);
  const assistant = useVoiceAssistant();
  useDataChannel(HUD_TOPIC, (message) => {
    const raw = new TextDecoder().decode(message.payload);
    setHud((current) => applyHudMessage(current, raw));
  });
  const tracks = useTracks([Track.Source.ScreenShare], { onlySubscribed: false });
  const shared = tracks.find((track) => track.publication);
  const thinking = hud.thinking || assistant.state === "thinking";
  return (
    <section aria-label="Shared screen" className="flex min-w-0 flex-col gap-2">
      <div className="relative aspect-video w-full overflow-hidden rounded-md border border-border bg-muted">
        {shared ? (
          <VideoTrack trackRef={shared} className="h-full w-full object-contain" />
        ) : (
          <p className="px-4 py-8 text-sm leading-6 text-muted-foreground">
            Share your screen so the agent can see it.
          </p>
        )}
        <ScreenHud thinking={thinking} point={hud.point} />
      </div>
      <p className="text-pretty text-sm leading-6 text-muted-foreground">
        The highlight is drawn on this preview. It does not move your mouse.
      </p>
    </section>
  );
}

function SessionBody() {
  const state = useConnectionState();
  const lines = transcriptLines(useTranscriptions());
  const label = state === ConnectionState.Connected ? "In the room" : "Connecting";
  return (
    <>
      <p role="status" className="text-sm text-muted-foreground">
        {label}
      </p>
      <div className="flex flex-wrap gap-3">
        <TrackToggle source={Track.Source.Microphone} aria-label="Microphone" />
        <TrackToggle source={Track.Source.ScreenShare} aria-label="Screen share" />
      </div>
      <ScreenStage />
      <TranscriptPanel lines={lines} />
    </>
  );
}
