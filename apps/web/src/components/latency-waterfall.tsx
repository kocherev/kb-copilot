import type { Turn } from "@/lib/api/client";
import { formatMs, stageLabels, stagesOf, totalMs } from "@/lib/replay";

// One colour per stage, so a bar reads the same on every row. The text beside
// each bar carries the same numbers for anyone who cannot tell the colours apart.
const STAGE_COLOR: Record<string, string> = {
  end_of_turn_delay_ms: "bg-chart-3",
  transcription_delay_ms: "bg-chart-2",
  search: "bg-chart-4",
  llm_ttft_ms: "bg-chart-1",
  tts_ttfb_ms: "bg-chart-5",
};

// Axis labels every half second up to a few seconds, every second past that,
// leaving out one so close to the end that its label would hang off the edge.
function ticks(widest: number): number[] {
  const step = widest > 3000 ? 1000 : 500;
  return Array.from({ length: Math.floor(widest / step) + 1 }, (_, index) => index * step).filter(
    (ms) => ms <= widest * 0.9,
  );
}

export function LatencyWaterfall({
  turns,
  agentName,
}: {
  turns: Turn[];
  agentName: string;
}) {
  const rows = turns.flatMap((turn, index) => {
    const stages = stagesOf(turn);
    if (stages.length === 0) {
      return [];
    }
    const total = totalMs(turn, stages);
    const sum = stages.reduce((all, stage) => all + stage.ms, 0);
    const speaker = turn.role === "user" ? "You" : agentName;
    return [{ id: turn.id, name: `Turn ${index + 1}, ${speaker}`, stages, total, sum }];
  });
  const widest = Math.max(1, ...rows.map((row) => row.sum));
  const grid = ticks(widest);

  if (rows.length === 0) {
    return (
      <p className="text-meta text-pretty text-muted-foreground">
        No latency was measured for this session.
      </p>
    );
  }
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <ul aria-label="Legend" className="flex list-none flex-wrap gap-x-3.5 gap-y-1.5 p-0">
        {stageLabels.map(([key, label]) => (
          <li key={key} className="flex items-center gap-1.5 text-meta text-muted-foreground">
            <span aria-hidden className={`size-2 rounded-full ${STAGE_COLOR[key]}`} />
            {label}
          </li>
        ))}
      </ul>
      <ol aria-label="Latency by turn" className="flex min-w-0 list-none flex-col gap-1 p-0">
        {rows.map((row, index) => {
          const detail = row.stages
            .map((stage) => `${stage.label} ${formatMs(stage.ms)}`)
            .join(", ");
          return (
            <li key={row.id} className="min-w-0">
              <a
                href={`#turn-${row.id}`}
                className="-mx-2 flex min-w-0 flex-col gap-1.5 rounded-control px-2 py-2 outline-none transition-colors duration-150 ease-out hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-ring"
              >
                <span className="flex justify-between gap-4 text-sm text-foreground">
                  <span className="[overflow-wrap:anywhere]">{row.name}</span>
                  <span className="font-mono text-meta tabular-nums text-muted-foreground">
                    {formatMs(row.total)}
                  </span>
                </span>
                <span className="relative block h-2.5 w-full overflow-hidden rounded-full bg-surface-sunken">
                  <span
                    role="img"
                    aria-label={detail}
                    // Grows from the left on first paint, one row after another.
                    style={{ transitionDelay: `${Math.min(index, 8) * 40}ms` }}
                    className="flex h-full origin-left gap-px transition-transform duration-300 ease-out motion-safe:starting:scale-x-0"
                  >
                    {row.stages.map((stage) => (
                      <span
                        key={stage.key}
                        className={`h-full min-w-0.5 first:rounded-l-full last:rounded-r-full ${STAGE_COLOR[stage.key]}`}
                        style={{ width: `${(stage.ms / widest) * 100}%` }}
                      />
                    ))}
                  </span>
                </span>
                <span className="text-meta leading-5 text-pretty text-muted-foreground tabular-nums">
                  {detail}
                </span>
              </a>
            </li>
          );
        })}
      </ol>
      <div aria-hidden className="relative h-4 border-t border-border text-[0.6875rem] text-subtle-foreground">
        {grid.map((ms) => (
          <span
            key={ms}
            className="absolute top-1 font-mono tabular-nums first:translate-x-0 -translate-x-1/2"
            style={{ left: `${(ms / widest) * 100}%` }}
          >
            {ms === 0 ? "0" : formatMs(ms)}
          </span>
        ))}
      </div>
    </div>
  );
}
