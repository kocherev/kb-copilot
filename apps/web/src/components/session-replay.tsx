import {
  AudioLines,
  BookOpen,
  Check,
  ChevronRight,
  CircleCheck,
  CircleSlash,
  Clock,
  ExternalLink,
  Flag,
  LifeBuoy,
  MessageSquareDashed,
  MousePointerClick,
  Search,
  Timer,
  TriangleAlert,
  User,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { LatencyWaterfall } from "@/components/latency-waterfall";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Section } from "@/components/ui/section";
import { Surface } from "@/components/ui/surface";
import type { Replay, Turn } from "@/lib/api/client";
import { stagger } from "@/lib/motion";
import {
  countLabel,
  eventLabel,
  formatDuration,
  formatMs,
  formatStart,
  median,
  offsetLabel,
  stagesOf,
  timeline,
  totalMs,
  type TimelineItem,
} from "@/lib/replay";
import { sourceLabel } from "@/lib/session";
import { cn } from "@/lib/utils";

const EVENT_STYLE: Record<string, { Icon: LucideIcon; className: string }> = {
  proposed: { Icon: MousePointerClick, className: "text-muted-foreground" },
  approved: { Icon: Check, className: "text-success" },
  performed: { Icon: CircleCheck, className: "text-success" },
  denied: { Icon: X, className: "text-destructive" },
  failed: { Icon: TriangleAlert, className: "text-destructive" },
  timed_out: { Icon: Clock, className: "text-warning" },
  ended: { Icon: Flag, className: "text-muted-foreground" },
};

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 px-4 py-3.5 sm:px-5">
      <dt className="text-overline text-muted-foreground uppercase">{label}</dt>
      <dd className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="font-display text-title tabular-nums text-foreground">{value}</span>
        {note ? <span className="text-meta text-muted-foreground">{note}</span> : null}
      </dd>
    </div>
  );
}

function Stats({ replay }: { replay: Replay }) {
  const searches = replay.turns.flatMap((turn) => turn.searches);
  const missed = searches.filter((search) => search.abstained).length;
  const replies = replay.turns.flatMap((turn) => {
    const stages = stagesOf(turn);
    return turn.role === "assistant" && stages.length > 0 ? [totalMs(turn, stages)] : [];
  });
  const typical = median(replies);
  const done = replay.actions.filter((action) => action.event === "performed").length;
  return (
    <Surface padding="none" className="animate-enter">
      <dl className="grid grid-cols-2 divide-border max-sm:[&>*:nth-child(n+3)]:border-t sm:grid-cols-4 sm:divide-x">
        <Stat
          label="Length"
          value={replay.ended_at ? formatDuration(replay.created_at, replay.ended_at) : "0:00"}
          note={countLabel(replay.turn_count, "turn")}
        />
        <Stat
          label="Median reply"
          value={typical === null ? "None" : formatMs(typical)}
          note={replies.length ? `over ${countLabel(replies.length, "answer")}` : undefined}
        />
        <Stat
          label="Searches"
          value={String(searches.length)}
          note={missed ? `${missed} found nothing` : undefined}
        />
        <Stat
          label="Desktop"
          value={String(done)}
          note={`${done === 1 ? "step" : "steps"} done${
            replay.handoffs.length ? `, ${countLabel(replay.handoffs.length, "handoff")}` : ""
          }`}
        />
      </dl>
    </Surface>
  );
}

function Searches({ turn }: { turn: Turn }) {
  const cited = new Set(turn.citations.map((citation) => citation.id));
  return (
    <ul aria-label="Searches" className="flex list-none flex-col gap-2 p-0">
      {turn.searches.map((search, index) => (
        <li key={index} className="min-w-0">
          <details className="group rounded-control bg-surface-sunken">
            <summary className="flex min-h-10 cursor-pointer list-none items-center gap-2 rounded-control px-3 py-2 text-sm outline-none transition-colors duration-150 ease-out hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
              <ChevronRight
                aria-hidden
                className="size-3.5 shrink-0 text-muted-foreground transition-transform duration-150 ease-out group-open:rotate-90 motion-reduce:transition-none"
              />
              <Search aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1 text-foreground [overflow-wrap:anywhere]">
                <span className="text-muted-foreground">Searched </span>
                &ldquo;{search.query}&rdquo;
              </span>
              {search.abstained ? (
                <span className="shrink-0 rounded-full bg-warning-soft px-2 py-0.5 text-meta text-warning">
                  No match
                </span>
              ) : (
                <span className="shrink-0 text-meta text-muted-foreground max-sm:sr-only">
                  {countLabel(search.passages.length, "passage")}
                </span>
              )}
              <span className="shrink-0 font-mono text-meta tabular-nums text-muted-foreground">
                {formatMs(search.duration_ms)}
              </span>
            </summary>
            <div className="px-3 pt-1 pb-3 group-open:animate-enter">
              {search.abstained ? (
                <p className="pb-2 text-meta text-pretty text-muted-foreground">
                  No passage scored high enough to answer from.
                </p>
              ) : null}
              {search.passages.length === 0 ? (
                <p className="text-meta text-muted-foreground">No passage came back.</p>
              ) : (
                <ol aria-label="Passages" className="flex list-none flex-col gap-2.5 p-0">
                  {search.passages.map((passage, rank) => (
                    <li
                      key={passage.id}
                      className="grid min-w-0 grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-x-2"
                    >
                      <span className="font-mono text-meta tabular-nums text-subtle-foreground">
                        {rank + 1}
                      </span>
                      <span className="flex min-w-0 flex-col">
                        <span className="flex min-w-0 flex-wrap items-center gap-x-2 text-sm text-foreground">
                          <span className="[overflow-wrap:anywhere]">{passage.title}</span>
                          {cited.has(passage.id) ? (
                            <span className="rounded-full bg-primary-soft px-1.5 text-meta text-primary-soft-foreground">
                              Cited
                            </span>
                          ) : null}
                        </span>
                        <span className="font-mono text-[0.75rem] text-muted-foreground [overflow-wrap:anywhere]">
                          {sourceLabel(passage.source)}
                        </span>
                      </span>
                      <span className="flex items-center gap-2">
                        <span aria-hidden className="h-1.5 w-12 overflow-hidden rounded-full bg-border sm:w-16">
                          <span
                            className={cn(
                              "block h-full rounded-full",
                              cited.has(passage.id) ? "bg-primary" : "bg-muted-foreground/50",
                            )}
                            style={{ width: `${Math.max(0, Math.min(1, passage.score)) * 100}%` }}
                          />
                        </span>
                        <span className="font-mono text-meta tabular-nums text-foreground">
                          {passage.score.toFixed(2)}
                        </span>
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </details>
        </li>
      ))}
    </ul>
  );
}

function Citations({ turn }: { turn: Turn }) {
  return (
    <ul aria-label="Cited" className="flex list-none flex-wrap gap-1.5 p-0">
      {turn.citations.map((passage) => (
        <li
          key={passage.id}
          className="flex min-w-0 items-center gap-1.5 rounded-full bg-primary-soft py-1 pr-2.5 pl-2 text-meta text-primary-soft-foreground"
        >
          <BookOpen aria-hidden className="size-3.5 shrink-0" />
          <span className="[overflow-wrap:anywhere]">{passage.title}</span>
          {passage.source ? (
            <span className="opacity-75 [overflow-wrap:anywhere]">{sourceLabel(passage.source)}</span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function Node({ Icon, className }: { Icon: LucideIcon; className: string }) {
  return (
    <span className={cn("relative grid size-8 shrink-0 place-items-center rounded-full", className)}>
      <Icon aria-hidden className="size-4" />
    </span>
  );
}

function Moment({
  item,
  replay,
  agentName,
}: {
  item: TimelineItem;
  replay: Replay;
  agentName: string;
}) {
  const at = (
    <span className="font-mono text-meta tabular-nums text-muted-foreground">
      {offsetLabel(replay.created_at, item.at)}
    </span>
  );
  if (item.kind === "turn") {
    const { turn } = item;
    const stages = stagesOf(turn);
    const agent = turn.role === "assistant";
    return (
      <>
        <Node
          Icon={agent ? AudioLines : User}
          className={agent ? "bg-primary-soft text-primary-soft-foreground" : "bg-surface-sunken text-muted-foreground shadow-ring"}
        />
        <div className="flex min-w-0 flex-col gap-2.5 pt-1">
          <p className="flex min-w-0 flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <span className="text-sm font-semibold text-foreground">{agent ? agentName : "You"}</span>
            {at}
            {agent && stages.length > 0 ? (
              <span className="flex items-center gap-1 text-meta text-muted-foreground">
                <Timer aria-hidden className="size-3.5" />
                Replied in {formatMs(totalMs(turn, stages))}
              </span>
            ) : null}
          </p>
          <p className="max-w-[65ch] text-body text-pretty text-foreground [overflow-wrap:anywhere]">
            {turn.text}
          </p>
          {turn.searches.length > 0 ? <Searches turn={turn} /> : null}
          {turn.citations.length > 0 ? <Citations turn={turn} /> : null}
        </div>
      </>
    );
  }
  if (item.kind === "task") {
    const done = item.steps.filter((step) => step.event === "performed").length;
    return (
      <>
        <Node Icon={MousePointerClick} className="bg-surface-sunken text-muted-foreground shadow-ring" />
        <div className="flex min-w-0 flex-col gap-2.5 pt-1">
          <p className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <span className="text-sm font-semibold text-foreground">Desktop task</span>
            {at}
            <span className="text-meta text-muted-foreground">
              {countLabel(done, "step")} done
            </span>
          </p>
          <ol
            aria-label="Desktop actions"
            className="flex min-w-0 list-none flex-col gap-0.5 rounded-control bg-surface-sunken p-1.5"
          >
            {item.steps.map((step, index) => {
              const { Icon, className } = EVENT_STYLE[step.event] ?? {
                Icon: CircleSlash,
                className: "text-muted-foreground",
              };
              return (
                <li
                  key={index}
                  className="grid min-w-0 grid-cols-[3rem_minmax(0,1fr)] items-baseline gap-x-2 px-2 py-1.5 text-sm sm:grid-cols-[3rem_6.5rem_minmax(0,1fr)]"
                >
                  <span className="font-mono text-meta tabular-nums text-muted-foreground">
                    {offsetLabel(replay.created_at, step.at)}
                  </span>
                  <span className="flex min-w-0 flex-col sm:contents">
                    <span className={cn("flex items-baseline gap-1.5 font-medium", className)}>
                      <Icon aria-hidden className="size-3.5 shrink-0 translate-y-0.5" />
                      {eventLabel(step.event)}
                    </span>
                    <span className="min-w-0 text-muted-foreground [overflow-wrap:anywhere]">
                      {step.detail}
                    </span>
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
      </>
    );
  }
  const { handoff } = item;
  return (
    <>
      <Node Icon={LifeBuoy} className="bg-warning-soft text-warning" />
      <div className="flex min-w-0 flex-col gap-1.5 pt-1">
        <p className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
          <span className="text-sm font-semibold text-foreground">Handed to a person</span>
          {at}
        </p>
        <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm text-foreground">
          <span className="[overflow-wrap:anywhere]">{handoff.title}</span>
          <span className="rounded-full bg-surface-sunken px-2 py-0.5 text-meta text-muted-foreground shadow-ring">
            {handoff.status}
          </span>
          {handoff.issue_identifier ? (
            handoff.issue_url ? (
              <a
                href={handoff.issue_url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 rounded-sm font-mono text-meta text-link underline decoration-foreground/30 underline-offset-4 outline-none hover:decoration-current focus-visible:outline-2 focus-visible:outline-ring"
              >
                {handoff.issue_identifier}
                <ExternalLink aria-hidden className="size-3" />
              </a>
            ) : (
              <span className="font-mono text-meta text-muted-foreground">{handoff.issue_identifier}</span>
            )
          ) : null}
        </p>
      </div>
    </>
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
  const items = timeline(replay);
  return (
    <main className="mx-auto flex w-full max-w-[1080px] min-w-0 flex-col gap-8 px-4 py-8 sm:gap-10 sm:px-8 sm:py-12">
      <PageHeader
        title={formatStart(replay.created_at)}
        back={{ href: `/products/${productId}`, label: productName }}
        description={
          <span className="font-mono text-meta [overflow-wrap:anywhere]">Room {replay.room}</span>
        }
      />
      {items.length === 0 ? (
        <EmptyState
          icon={MessageSquareDashed}
          title="Nothing to replay"
          description={`No one spoke in this session, so there is nothing to show. Start a session and talk to ${agentName} to record one.`}
          action={
            <Button variant="outline" render={<Link href={`/products/${productId}/session`} />}>
              Start a session
            </Button>
          }
        />
      ) : (
        <>
          <Stats replay={replay} />
          <div className="grid min-w-0 gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)] lg:gap-12">
            <Section title="Timeline" description="What was said, what was searched, and what happened on the Mac.">
              <ol aria-label="Timeline" className="flex min-w-0 list-none flex-col p-0">
                {items.map((item, index) => (
                  <li
                    key={`${item.kind}-${item.at}-${index}`}
                    id={item.kind === "turn" ? `turn-${item.turn.id}` : undefined}
                    style={stagger(index)}
                    className="group/moment relative grid min-w-0 scroll-mt-20 grid-cols-[2rem_minmax(0,1fr)] gap-x-3.5 pb-7 animate-enter last:pb-0 sm:gap-x-4"
                  >
                    {/* The rail between nodes. */}
                    <span
                      aria-hidden
                      className="absolute top-9 bottom-1 left-4 w-px -translate-x-1/2 bg-border group-last/moment:hidden"
                    />
                    <Moment item={item} replay={replay} agentName={agentName} />
                  </li>
                ))}
              </ol>
            </Section>
            <Surface className="h-fit lg:sticky lg:top-20">
              <Section title="Latency" description="From the end of speech to the first audio, by stage.">
                <LatencyWaterfall turns={replay.turns} agentName={agentName} />
              </Section>
            </Surface>
          </div>
        </>
      )}
    </main>
  );
}
