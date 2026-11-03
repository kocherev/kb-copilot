"use client";

import { Check, Copy, Laptop } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/inline-error";
import { Spinner } from "@/components/ui/spinner";
import { browserApi, errorDetail } from "@/lib/api/client";

function helperCommand(url: string, token: string): string {
  return `uv run --package kb-desktop kb-desktop --url ${url} --token ${token}`;
}

const swap =
  "absolute inset-0 size-4 transition-[opacity,scale,filter] duration-300 ease-[cubic-bezier(0.2,0,0,1)]";
const hidden = "opacity-0 motion-safe:scale-25 motion-safe:blur-[4px]";

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
      setError("Could not get the command. Check that the API is running, then try again.");
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
    <section
      aria-label="Your Mac"
      className="flex min-w-0 flex-col gap-3 rounded-card border border-transparent bg-surface p-4 shadow-soft"
    >
      <div className="flex min-w-0 items-start gap-3">
        <span
          className={`relative grid size-9 shrink-0 place-items-center rounded-full ${connected ? "bg-success-soft text-success" : "bg-surface-sunken text-muted-foreground"}`}
        >
          <Laptop aria-hidden className="size-4" />
          {connected ? (
            <span
              aria-hidden
              className="absolute -right-0.5 -bottom-0.5 size-3 rounded-full border-2 border-surface bg-success"
            />
          ) : null}
        </span>
        <div className="flex min-w-0 flex-col gap-0.5">
          <h2 className="text-sm font-medium text-foreground">Your Mac</h2>
          <p role="status" className="text-meta text-pretty text-muted-foreground">
            {connected
              ? `Your Mac is connected. ${agentName} asks before every click or keystroke.`
              : `Your Mac is not connected. ${agentName} can point, not click.`}
          </p>
        </div>
      </div>
      {connected ? null : (
        <>
          <p className="text-meta text-pretty text-muted-foreground">
            To let {agentName} act, run this from the repository root on your Mac. The command
            works for ten minutes.
          </p>
          {command ? (
            <div className="relative min-w-0 rounded-control bg-surface-sunken">
              <code className="block py-2.5 pr-12 pl-3 font-mono text-xs leading-5 text-foreground [overflow-wrap:anywhere]">
                {command}
              </code>
              <button
                type="button"
                aria-label={copied ? "Copied" : "Copy command"}
                title={copied ? "Copied" : "Copy command"}
                onClick={() => void copy(command)}
                className="absolute top-1.5 right-1.5 grid size-8 place-items-center rounded-md text-muted-foreground transition-[scale,background-color,color] duration-150 ease-out outline-none hover:bg-surface-hover hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring motion-safe:active:scale-[0.96] pointer-coarse:after:absolute pointer-coarse:after:size-11"
              >
                <span aria-hidden className="relative size-4">
                  <Copy className={`${swap} ${copied ? hidden : ""}`} />
                  <Check className={`${swap} text-success ${copied ? "" : hidden}`} />
                </span>
              </button>
            </div>
          ) : (
            <Button
              type="button"
              variant="outline"
              disabled={pending}
              onClick={() => void mint()}
            >
              {pending ? <Spinner /> : null}
              {pending ? "Getting the command…" : "Connect your Mac"}
            </Button>
          )}
          {error ? <InlineError>{error}</InlineError> : null}
        </>
      )}
    </section>
  );
}
