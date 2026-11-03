"use client";

import { useCallback, useEffect, useState } from "react";

import { PendingLabel } from "@/components/product-form";
import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/inline-error";
import { InlineStatus } from "@/components/ui/inline-status";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { Surface } from "@/components/ui/surface";
import { browserApi, errorDetail, type LinearStatus } from "@/lib/api/client";
import type { LinearNotice } from "@/lib/linear";

const notices: Record<LinearNotice, { tone: "success" | "warning"; text: string }> = {
  connected: { tone: "success", text: "Linear connected." },
  denied: { tone: "warning", text: "Linear access was not granted." },
  failed: { tone: "warning", text: "Couldn’t connect Linear. Try again." },
};

async function fetchStatus(apiUrl: string): Promise<LinearStatus | null> {
  try {
    const { data } = await browserApi(apiUrl).GET("/integrations/linear");
    return data ?? null;
  } catch {
    return null;
  }
}

export function LinearSkeleton() {
  return (
    <Surface>
      <Loading label="Loading the Linear connection" className="flex min-w-0 flex-col gap-3">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3.5 w-3/4" />
        <Skeleton className="mt-2 h-8 w-36 rounded-control" />
      </Loading>
    </Surface>
  );
}

export function LinearConnection({
  apiUrl,
  notice,
}: {
  apiUrl: string;
  notice: LinearNotice | null;
}) {
  const [status, setStatus] = useState<LinearStatus | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // The callback's outcome describes the connection it made, so it goes
  // when that connection does.
  const [shownNotice, setShownNotice] = useState(notice);

  const refresh = useCallback(
    () =>
      fetchStatus(apiUrl).then((data) => {
        setLoadError(data === null);
        if (data) {
          setStatus(data);
        }
      }),
    [apiUrl],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function retry() {
    setLoadError(false);
    setStatus(null);
    void refresh();
  }

  async function connect() {
    if (pending) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      const { data, error: detail } = await browserApi(apiUrl).GET(
        "/integrations/linear/connect",
      );
      if (!data) {
        setError(errorDetail(detail, "Couldn’t start the Linear connection. Try again."));
        setPending(false);
        return;
      }
      // Stay pending while the browser leaves for Linear.
      window.location.assign(data.url);
    } catch {
      setError("Couldn’t start the Linear connection. Try again.");
      setPending(false);
    }
  }

  async function disconnect() {
    if (pending) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      const { response, error: detail } = await browserApi(apiUrl).DELETE(
        "/integrations/linear",
      );
      if (!response.ok) {
        setError(errorDetail(detail, "Couldn’t disconnect Linear. Try again."));
        return;
      }
      setShownNotice(null);
      await refresh();
    } catch {
      setError("Couldn’t disconnect Linear. Try again.");
    } finally {
      setPending(false);
    }
  }

  if (loadError) {
    return (
      <InlineError onRetry={retry}>
        Couldn’t load the Linear connection. Check that the API is running, then try again.
      </InlineError>
    );
  }
  if (status === null) {
    return <LinearSkeleton />;
  }
  return (
    <Surface className="flex min-w-0 animate-enter flex-col gap-4">
      {shownNotice ? (
        <InlineStatus tone={notices[shownNotice].tone}>{notices[shownNotice].text}</InlineStatus>
      ) : null}
      {!status.enabled ? (
        <p className="text-sm text-pretty text-muted-foreground">
          Linear isn’t set up on this server. Set <Code>LINEAR_CLIENT_ID</Code>,{" "}
          <Code>LINEAR_CLIENT_SECRET</Code> and <Code>LINEAR_TOKEN_KEY</Code> for the API, then
          restart it.
        </p>
      ) : status.connected ? (
        <>
          <div className="flex min-w-0 flex-col gap-1">
            <StateLabel connected />
            <p className="text-sm text-pretty text-foreground [overflow-wrap:anywhere]">
              Connected to {status.workspace_name}. Tickets go to {status.team_name} (
              {status.team_key}).
            </p>
          </div>
          <Button
            variant="destructive-outline"
            aria-disabled={pending}
            onClick={() => void disconnect()}
          >
            <PendingLabel pending={pending} label="Disconnect Linear" pendingLabel="Disconnecting…" />
          </Button>
        </>
      ) : (
        <>
          <div className="flex min-w-0 flex-col gap-1">
            <StateLabel connected={false} />
            <p className="text-sm text-pretty text-muted-foreground">
              Connect a workspace to let the agent file tickets there.
            </p>
          </div>
          <Button aria-disabled={pending} onClick={() => void connect()}>
            <PendingLabel pending={pending} label="Connect Linear" pendingLabel="Opening Linear…" />
          </Button>
        </>
      )}
      {error ? <InlineError>{error}</InlineError> : null}
    </Surface>
  );
}

function StateLabel({ connected }: { connected: boolean }) {
  return (
    <p className="flex items-center gap-2 text-sm font-medium text-foreground">
      <span
        aria-hidden
        className={`size-2 rounded-full ${connected ? "bg-success" : "bg-subtle-foreground"}`}
      />
      {connected ? "Connected" : "Not connected"}
    </p>
  );
}

function Code({ children }: { children: string }) {
  return (
    <code className="rounded-md bg-surface-sunken px-1.5 py-0.5 font-mono text-[0.8125em] text-foreground">
      {children}
    </code>
  );
}
