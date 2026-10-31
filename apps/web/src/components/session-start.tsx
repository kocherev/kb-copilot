"use client";

import {
  LiveKitRoom,
  RoomAudioRenderer,
  TrackToggle,
  useConnectionState,
  useTranscriptions,
} from "@livekit/components-react";
import { ConnectionState, Track } from "livekit-client";
import Link from "next/link";
import { useState } from "react";

import { TranscriptPanel } from "@/components/transcript-panel";
import { Button } from "@/components/ui/button";
import { apiPath, readJson } from "@/lib/api";
import {
  sessionFromResponse,
  sessionPublish,
  transcriptLines,
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
    <main className="mx-auto flex min-h-dvh w-full max-w-lg min-w-0 flex-col gap-8 px-6 py-16">
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
  return (
    <LiveKitRoom
      serverUrl={url}
      token={token}
      connect
      audio={sessionPublish.audio}
      video={sessionPublish.video}
      screen={sessionPublish.screen}
      className="flex min-w-0 flex-col gap-6"
    >
      <RoomAudioRenderer />
      <SessionBody />
    </LiveKitRoom>
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
      <TranscriptPanel lines={lines} />
    </>
  );
}
