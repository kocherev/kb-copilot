import Link from "next/link";

import { LatencyWaterfall } from "@/components/latency-waterfall";
import type { Replay, Turn } from "@/lib/api/client";
import {
  eventLabel,
  formatMs,
  formatStart,
  offsetLabel,
  summaryLine,
} from "@/lib/replay";
import { sourceLabel } from "@/lib/session";

const linkClass =
  "text-sm underline underline-offset-4 focus-visible:[outline:var(--hui-focus-ring)] focus-visible:outline-offset-[var(--hui-focus-ring-offset-accent)]";

function Searches({ searches }: { searches: Turn["searches"] }) {
  return (
    <ul aria-label="Searches" className="flex list-none flex-col gap-2 p-0">
      {searches.map((search, index) => (
        <li
          key={index}
          className="border-l-2 border-border py-0.5 pl-3 text-sm leading-6 text-muted-foreground [overflow-wrap:anywhere]"
        >
          <details>
            <summary className="cursor-pointer">
              Searched for &ldquo;{search.query}&rdquo;
              <span className="text-xs tabular-nums">
                {" "}
                ({search.abstained ? "no match, " : ""}
                {formatMs(search.duration_ms)})
              </span>
            </summary>
            {search.passages.length === 0 ? (
              <p className="mt-1">No passage came back.</p>
            ) : (
              <ol className="mt-1 flex list-none flex-col gap-1 p-0">
                {search.passages.map((passage) => (
                  <li key={passage.id} className="flex justify-between gap-4">
                    <span>
                      {passage.title}{" "}
                      <span className="text-xs">({sourceLabel(passage.source)})</span>
                    </span>
                    <span className="tabular-nums">{passage.score.toFixed(2)}</span>
                  </li>
                ))}
              </ol>
            )}
          </details>
        </li>
      ))}
    </ul>
  );
}

export function SessionReplay({
  replay,
  productId,
  productName,
  agentName,
}: {
  replay: Replay;
  productId: string;
  productName: string;
  agentName: string;
}) {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-2xl min-w-0 flex-col gap-8 px-6 py-16">
      <Link className={linkClass} href={`/products/${productId}`}>
        {productName}
      </Link>
      <div className="flex flex-col gap-1">
        <h1 className="text-balance text-2xl font-medium tracking-tight text-foreground">
          {formatStart(replay.created_at)}
        </h1>
        <p className="text-sm leading-6 text-muted-foreground tabular-nums">
          {summaryLine(replay)}
        </p>
        <p className="font-mono text-xs leading-5 text-muted-foreground [overflow-wrap:anywhere]">
          Room {replay.room}
        </p>
      </div>
      {replay.turns.length === 0 ? (
        <p className="text-pretty text-sm leading-6 text-muted-foreground">
          Nothing was said in this session, so there is nothing to replay.
        </p>
      ) : (
        <>
          <section aria-labelledby="transcript-heading" className="flex min-w-0 flex-col gap-4">
            <h2 id="transcript-heading" className="text-balance text-sm font-medium text-foreground">
              Transcript
            </h2>
            <ol aria-label="Turns" className="flex min-w-0 list-none flex-col gap-5 p-0">
              {replay.turns.map((turn) => (
                <li key={turn.id} className="flex min-w-0 flex-col gap-1">
                  <p className="flex gap-2 text-sm font-medium text-foreground">
                    {turn.role === "user" ? "You" : agentName}
                    <span className="font-normal tabular-nums text-muted-foreground">
                      {offsetLabel(replay.created_at, turn.started_at)}
                    </span>
                  </p>
                  <p className="text-sm leading-6 text-foreground [overflow-wrap:anywhere]">
                    {turn.text}
                  </p>
                  {turn.searches.length > 0 ? <Searches searches={turn.searches} /> : null}
                  {turn.citations.length > 0 ? (
                    <ul aria-label="Cited" className="flex list-none flex-col gap-1 p-0">
                      {turn.citations.map((passage) => (
                        <li
                          key={passage.id}
                          className="text-sm leading-6 text-muted-foreground [overflow-wrap:anywhere]"
                        >
                          Cited {passage.title}
                          {passage.source ? (
                            <span className="text-xs"> ({sourceLabel(passage.source)})</span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ol>
          </section>
          <LatencyWaterfall turns={replay.turns} agentName={agentName} />
        </>
      )}
      {replay.actions.length > 0 ? (
        <section aria-labelledby="actions-heading" className="flex min-w-0 flex-col gap-3">
          <h2 id="actions-heading" className="text-balance text-sm font-medium text-foreground">
            Desktop actions
          </h2>
          <ol aria-label="Desktop actions" className="flex min-w-0 list-none flex-col gap-2 p-0">
            {replay.actions.map((action, index) => (
              <li key={index} className="flex min-w-0 gap-3 text-sm leading-6">
                <span className="shrink-0 tabular-nums text-muted-foreground">
                  {offsetLabel(replay.created_at, action.at)}
                </span>
                <span className="font-medium text-foreground">{eventLabel(action.event)}</span>
                <span className="min-w-0 text-muted-foreground [overflow-wrap:anywhere]">
                  {action.detail}
                </span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
      {replay.handoffs.length > 0 ? (
        <section aria-labelledby="handoffs-heading" className="flex min-w-0 flex-col gap-3">
          <h2 id="handoffs-heading" className="text-balance text-sm font-medium text-foreground">
            Handoffs
          </h2>
          <ul aria-label="Handoffs" className="flex min-w-0 list-none flex-col gap-2 p-0">
            {replay.handoffs.map((handoff) => (
              <li
                key={handoff.created_at}
                className="text-sm leading-6 text-foreground [overflow-wrap:anywhere]"
              >
                {handoff.title}{" "}
                <span className="text-muted-foreground">
                  ({handoff.status}
                  {handoff.issue_identifier ? `, ${handoff.issue_identifier}` : ""})
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </main>
  );
}
