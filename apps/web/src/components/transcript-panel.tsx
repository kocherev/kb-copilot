import type { TranscriptLine } from "@/lib/session";

export function TranscriptPanel({ lines }: { lines: TranscriptLine[] }) {
  return (
    <section aria-label="Transcript" className="flex min-w-0 flex-col gap-3">
      <h2 className="text-sm font-medium text-foreground">Transcript</h2>
      {lines.length === 0 ? (
        <p className="text-sm leading-6 text-muted-foreground">Waiting for speech.</p>
      ) : (
        <ol className="flex min-w-0 list-none flex-col gap-3 p-0">
          {lines.map((line) => (
            <li key={line.id} className="min-w-0">
              <p className="text-sm font-medium text-foreground">{line.speaker}</p>
              <p className="text-sm leading-6 text-foreground [overflow-wrap:anywhere]">
                {line.text}
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
