"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { browserApi, errorDetail } from "@/lib/api/client";

export function helperCommand(url: string, token: string): string {
  return `uv run --package kb-desktop kb-desktop --url ${url} --token ${token}`;
}

// Shows whether the desktop helper is in the room, and mints the one command
// that starts it for this session.
export function ConnectMac({
  apiUrl,
  room,
  agentName,
  connected,
}: {
  apiUrl: string;
  room: string;
  agentName: string;
  connected: boolean;
}) {
  const [command, setCommand] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [copied, setCopied] = useState(false);

  async function mint() {
    setPending(true);
    setError(null);
    try {
      const { data, error } = await browserApi(apiUrl).POST("/sessions/{room}/desktop-token", {
        params: { path: { room } },
      });
      if (data) {
        setCommand(helperCommand(data.url, data.token));
        setCopied(false);
      } else {
        setError(errorDetail(error, "Could not get the command."));
      }
    } catch {
      setError("Could not get the command.");
    } finally {
      setPending(false);
    }
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setError("Copy failed. Select the command and copy it.");
    }
  }

  return (
    <section aria-label="Your Mac" className="flex min-w-0 flex-col gap-3">
      <p role="status" className="text-pretty text-sm leading-6 text-foreground">
        {connected
          ? `Your Mac is connected. ${agentName} asks before every click or keystroke.`
          : `Your Mac is not connected. ${agentName} can point, not click.`}
      </p>
      {connected ? null : (
        <>
          <p className="text-pretty text-sm leading-6 text-muted-foreground">
            To let {agentName} act, run this from the repository root on your Mac. The
            command works for ten minutes.
          </p>
          {command ? (
            <>
              <code className="block rounded-md bg-muted p-3 font-mono text-xs leading-5 text-foreground [overflow-wrap:anywhere]">
                {command}
              </code>
              <Button type="button" variant="outline" onClick={() => void copy(command)}>
                {copied ? "Copied" : "Copy command"}
              </Button>
            </>
          ) : (
            <Button type="button" variant="outline" disabled={pending} onClick={() => void mint()}>
              Connect your Mac
            </Button>
          )}
          {error ? (
            <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
              {error}
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
