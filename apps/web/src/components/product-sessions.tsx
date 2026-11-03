"use client";

import { ChevronRight, History } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { InlineError } from "@/components/ui/inline-error";
import { Section } from "@/components/ui/section";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { Surface } from "@/components/ui/surface";
import { browserApi, type SessionSummary } from "@/lib/api/client";
import { stagger } from "@/lib/motion";
import { formatStart, sessionFacts } from "@/lib/replay";

type Load =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; sessions: SessionSummary[] };

async function fetchSessions(apiUrl: string, productId: string): Promise<Load> {
  try {
    const { data } = await browserApi(apiUrl).GET("/sessions", {
      params: { query: { product_id: productId } },
    });
    return data ? { status: "ready", sessions: data } : { status: "error" };
  } catch {
    return { status: "error" };
  }
}

export function ProductSessions({
  apiUrl,
  productId,
  agentName,
  className,
}: {
  apiUrl: string;
  productId: string;
  agentName: string;
  className?: string;
}) {
  const [load, setLoad] = useState<Load>({ status: "loading" });

  const refresh = useCallback(
    () => fetchSessions(apiUrl, productId).then(setLoad),
    [apiUrl, productId],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <Section
      title="Sessions"
      description="Each one leaves a replay: what was said, what was searched, and how fast the answers came."
      className={className}
    >
      {load.status === "loading" ? (
        <Loading label="Loading sessions">
          <Surface padding="none" className="divide-y divide-border">
            {[0, 1, 2].map((row) => (
              <div key={row} className="flex flex-col gap-2 px-4 py-3.5">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-3.5 w-36" />
              </div>
            ))}
          </Surface>
        </Loading>
      ) : null}
      {load.status === "error" ? (
        <InlineError onRetry={() => void refresh()}>
          Couldn&rsquo;t load sessions. Check the API is running, then try again.
        </InlineError>
      ) : null}
      {load.status === "ready" && load.sessions.length === 0 ? (
        <EmptyState
          icon={History}
          title="No sessions yet"
          description={`Start a session and talk to ${agentName}. Each one leaves a replay here.`}
        />
      ) : null}
      {load.status === "ready" && load.sessions.length > 0 ? (
        <Surface padding="none">
          <ul aria-label="Sessions" className="flex min-w-0 list-none flex-col p-1.5">
            {load.sessions.map((session, index) => (
              <li key={session.id} style={stagger(index)} className="min-w-0 animate-enter">
                <Link
                  href={`/products/${productId}/sessions/${session.id}`}
                  className="group flex min-w-0 items-center gap-3 rounded-control px-3 py-2.5 outline-none transition-colors duration-150 ease-out hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-ring"
                >
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="text-sm font-medium text-foreground">
                      {formatStart(session.created_at)}
                    </span>
                    <span className="flex min-w-0 flex-wrap gap-x-1.5 text-meta tabular-nums text-muted-foreground">
                      {sessionFacts(session).map((fact, at) => (
                        <span key={fact}>
                          {at > 0 ? (
                            <span aria-hidden className="mr-1.5 text-subtle-foreground">
                              ·
                            </span>
                          ) : null}
                          {fact}
                        </span>
                      ))}
                    </span>
                  </span>
                  <ChevronRight
                    aria-hidden
                    className="size-4 shrink-0 text-subtle-foreground transition-colors duration-150 ease-out group-hover:text-muted-foreground"
                  />
                </Link>
              </li>
            ))}
          </ul>
        </Surface>
      ) : null}
    </Section>
  );
}
