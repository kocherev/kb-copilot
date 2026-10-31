import { sourceLabel, type TranscriptLine } from "@/lib/session";

export function TranscriptPanel({ lines }: { lines: TranscriptLine[] }) {
  return (
    <section aria-label="Transcript" className="flex min-w-0 flex-col gap-3">
      <h2 className="text-sm font-medium text-foreground">Transcript</h2>
      {lines.length === 0 ? (
        <div className="flex flex-col gap-2">
          <p className="text-sm leading-6 text-muted-foreground">Waiting for speech.</p>
          <p className="text-pretty text-sm leading-6 text-muted-foreground">
            A cited answer shows Source: and the file name.
          </p>
        </div>
      ) : (
        <ol className="flex min-w-0 list-none flex-col gap-4 p-0">
          {lines.map((line) => (
            <li key={line.id} className="flex min-w-0 flex-col gap-1">
              <p className="text-sm font-medium text-foreground">{line.speaker}</p>
              {line.text ? (
                <p className="text-sm leading-6 text-foreground [overflow-wrap:anywhere]">
                  {line.text}
                </p>
              ) : null}
              {line.sources.length > 0 ? (
                <ul aria-label="Sources" className="mt-1 flex list-none flex-col gap-2 p-0">
                  {line.sources.map((source) => (
                    <li
                      key={source}
                      title={source}
                      className="border-l-2 border-border py-0.5 pl-3 text-sm leading-6 text-muted-foreground [overflow-wrap:anywhere]"
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
