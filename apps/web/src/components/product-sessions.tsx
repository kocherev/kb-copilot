"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { browserApi, type SessionSummary } from "@/lib/api/client";
import { formatStart, summaryLine } from "@/lib/replay";

const linkClass =
  "text-sm underline underline-offset-4 focus-visible:[outline:var(--hui-focus-ring)] focus-visible:outline-offset-[var(--hui-focus-ring-offset-accent)]";

async function fetchSessions(
  apiUrl: string,
  productId: string,
): Promise<SessionSummary[] | null> {
  try {
    const { data } = await browserApi(apiUrl).GET("/sessions", {
      params: { query: { product_id: productId } },
    });
    return data ?? null;
  } catch {
    return null;
  }
}

export function ProductSessions({
  apiUrl,
  productId,
}: {
  apiUrl: string;
  productId: string;
}) {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    void fetchSessions(apiUrl, productId).then((data) => {
      setLoadError(data === null);
      setSessions(data);
    });
  }, [apiUrl, productId]);

  return (
    <section aria-labelledby="sessions-heading" className="flex min-w-0 flex-col gap-4">
      <h2 id="sessions-heading" className="text-balance text-sm font-medium text-foreground">
        Sessions
      </h2>
      {loadError ? (
        <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
          Could not load sessions.
        </p>
      ) : null}
      {sessions === null && !loadError ? (
        <p className="text-sm leading-6 text-muted-foreground">Loading sessions.</p>
      ) : null}
      {sessions?.length === 0 ? (
        <p className="text-pretty text-sm leading-6 text-muted-foreground">
          No sessions yet. Each one you start leaves a replay here.
        </p>
      ) : null}
      {sessions && sessions.length > 0 ? (
        <ul aria-label="Sessions" className="flex min-w-0 list-none flex-col gap-3 p-0">
          {sessions.map((session) => (
            <li key={session.id} className="flex min-w-0 flex-col gap-0.5">
              <Link
                className={linkClass}
                href={`/products/${productId}/sessions/${session.id}`}
              >
                {formatStart(session.created_at)}
              </Link>
              <p className="text-sm leading-6 text-muted-foreground tabular-nums">
                {summaryLine(session)}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
