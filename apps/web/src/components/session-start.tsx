"use client";

import Link from "next/link";
import { useState } from "react";

import { SessionRoom } from "@/components/session-room";
import { Button } from "@/components/ui/button";
import { browserApi, type SessionGrant } from "@/lib/api/client";
import { sessionLoad } from "@/lib/session";

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
      const { data, error, response } = await browserApi(apiUrl).POST("/sessions", {
        body: { product_id: productId },
      });
      const loaded = sessionLoad(response.status, data, error);
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
        <SessionRoom
          url={session.url}
          token={session.token}
          onRestart={() => setSession(null)}
        />
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
