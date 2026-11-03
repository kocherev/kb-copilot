import { BookOpen, ChevronDown, FileText, MessagesSquare } from "lucide-react";

import type { CitedPassage } from "@/lib/protocol";
import { sourceLabel, type TranscriptLine } from "@/lib/session";

function Sources({ passages }: { passages: CitedPassage[] }) {
  return (
    <ul aria-label="Sources" className="flex min-w-0 list-none flex-wrap gap-1.5 p-0">
      {passages.map((passage) => (
        <li key={passage.id} className="min-w-0 max-w-full has-[details[open]]:basis-full">
          <details className="group min-w-0">
            <summary
              title={passage.title}
              className="flex w-fit max-w-full cursor-pointer list-none items-center gap-1.5 rounded-full bg-surface-sunken px-2.5 py-1 text-meta text-muted-foreground transition-colors duration-150 ease-out outline-none select-none hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring group-open:bg-primary-soft group-open:text-primary-soft-foreground pointer-coarse:py-2 [&::-webkit-details-marker]:hidden"
            >
              <BookOpen aria-hidden className="size-3.5 shrink-0" />
              <span className="min-w-0 truncate">{passage.title}</span>
              <ChevronDown
                aria-hidden
                className="size-3.5 shrink-0 transition-transform duration-150 ease-out group-open:rotate-180"
              />
            </summary>
            <div className="mt-1.5 flex min-w-0 flex-col gap-1.5 rounded-control bg-surface-sunken px-3 py-2.5 group-open:animate-enter group-open:[--motion-y:-4px] motion-reduce:group-open:[--motion-y:0px]">
              <p className="text-meta text-pretty text-foreground [overflow-wrap:anywhere]">
                {passage.snippet}
              </p>
              <p className="flex min-w-0 items-start gap-1 font-mono text-xs text-muted-foreground">
                <FileText aria-hidden className="mt-px size-3.5 shrink-0" />
                <span className="min-w-0 [overflow-wrap:anywhere]">{sourceLabel(passage.source)}</span>
              </p>
            </div>
          </details>
        </li>
      ))}
    </ul>
  );
}

// The log is the only child of a reversed column, so the browser keeps it
// scrolled to the newest line unless the reader scrolls up.
export function TranscriptPanel({
  lines,
  agentName,
}: {
  lines: TranscriptLine[];
  agentName: string;
}) {
  return (
    <section
      aria-label="Transcript"
      className="flex min-h-0 min-w-0 flex-col rounded-card border border-transparent bg-surface shadow-soft"
    >
      <h2 className="px-4 pt-4 pb-3 text-heading text-foreground">Transcript</h2>
      {lines.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-6 pt-4 pb-8 text-center">
          <span className="grid size-10 place-items-center rounded-full bg-primary-soft text-primary-soft-foreground">
            <MessagesSquare aria-hidden className="size-5" />
          </span>
          <p className="font-display text-lg/tight text-foreground">Nothing said yet</p>
          <p className="max-w-[34ch] text-meta text-pretty text-muted-foreground">
            Ask {agentName} a question out loud. Answers from your docs list their sources here.
          </p>
        </div>
      ) : null}
      <div className="flex min-h-0 flex-col-reverse overflow-y-auto overscroll-contain">
        <ol
          role="log"
          aria-label="Conversation"
          aria-live="polite"
          className="flex min-w-0 list-none flex-col gap-4 px-4 pb-4 empty:p-0"
        >
          {lines.map((line) => {
            const agent = line.speaker === "Agent";
            return (
              <li
                key={line.id}
                className={`flex min-w-0 flex-col gap-1.5 animate-enter ${agent ? "items-start" : "items-end"}`}
              >
                <p
                  className={`text-meta font-medium ${agent ? "text-primary-soft-foreground" : "text-muted-foreground"}`}
                >
                  {agent ? agentName : line.speaker}
                </p>
                <p
                  className={`max-w-full text-body text-pretty text-foreground [overflow-wrap:anywhere] ${agent ? "" : "rounded-card rounded-tr-md bg-surface-sunken px-3 py-2"}`}
                >
                  {line.text}
                </p>
                {line.citations.length > 0 ? <Sources passages={line.citations} /> : null}
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
