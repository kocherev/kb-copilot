"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { browserApi, errorDetail, type LinearStatus } from "@/lib/api/client";
import type { LinearNotice } from "@/lib/linear";

const notices: Record<LinearNotice, string> = {
  connected: "Linear connected.",
  denied: "Linear access was not granted.",
  failed: "Could not connect Linear. Try again.",
};

async function fetchStatus(apiUrl: string): Promise<LinearStatus | null> {
  try {
    const { data } = await browserApi(apiUrl).GET("/integrations/linear");
    return data ?? null;
  } catch {
    return null;
  }
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

  async function connect() {
    setPending(true);
    setError(null);
    try {
      const { data, error: detail } = await browserApi(apiUrl).GET(
        "/integrations/linear/connect",
      );
      if (!data) {
        setError(errorDetail(detail, "Could not start the Linear connection."));
        return;
      }
      window.location.assign(data.url);
    } catch {
      setError("Could not start the Linear connection.");
    } finally {
      setPending(false);
    }
  }

  async function disconnect() {
    setPending(true);
    setError(null);
    try {
      const { response, error: detail } = await browserApi(apiUrl).DELETE(
        "/integrations/linear",
      );
      if (!response.ok) {
        setError(errorDetail(detail, "Could not disconnect Linear."));
        return;
      }
      await refresh();
    } catch {
      setError("Could not disconnect Linear.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section aria-labelledby="linear-heading" className="flex min-w-0 flex-col gap-4">
      <h2 id="linear-heading" className="text-balance text-sm font-medium text-foreground">
        Linear
      </h2>
      <p className="text-pretty text-sm leading-6 text-muted-foreground">
        When the agent cannot solve a problem, it can propose a Linear ticket. You
        approve each ticket on the session page before it is created.
      </p>
      {notice ? (
        <p role="status" className="text-pretty text-sm leading-6 text-foreground">
          {notices[notice]}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
          {error}
        </p>
      ) : null}
      {loadError ? (
        <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
          Could not load the Linear connection.
        </p>
      ) : null}
      {status === null && !loadError ? (
        <p className="text-sm leading-6 text-muted-foreground">Loading.</p>
      ) : null}
      {status && !status.enabled ? (
        <p className="text-pretty text-sm leading-6 text-muted-foreground">
          Linear is not set up on this server. Set LINEAR_CLIENT_ID,
          LINEAR_CLIENT_SECRET, and LINEAR_TOKEN_KEY.
        </p>
      ) : null}
      {status?.enabled && status.connected ? (
        <>
          <p className="text-pretty text-sm leading-6 text-foreground [overflow-wrap:anywhere]">
            Connected to {status.workspace_name}. Tickets go to {status.team_name} (
            {status.team_key}).
          </p>
          <Button type="button" variant="outline" disabled={pending} onClick={() => void disconnect()}>
            Disconnect Linear
          </Button>
        </>
      ) : null}
      {status?.enabled && !status.connected ? (
        <Button type="button" disabled={pending} onClick={() => void connect()}>
          Connect Linear
        </Button>
      ) : null}
    </section>
  );
}
