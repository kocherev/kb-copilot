import { sourceLabel, type TranscriptLine } from "@/lib/session";

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
              {line.text ? (
                <p className="text-sm leading-6 text-foreground [overflow-wrap:anywhere]">
                  {line.text}
                </p>
              ) : null}
              {line.sources.length > 0 ? (
                <ul aria-label="Sources" className="mt-1 flex list-none flex-col gap-1 p-0">
                  {line.sources.map((source) => (
                    <li
                      key={source}
                      title={source}
                      className="text-sm leading-6 text-muted-foreground [overflow-wrap:anywhere]"
                    >
                      Source: {sourceLabel(source)}
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
