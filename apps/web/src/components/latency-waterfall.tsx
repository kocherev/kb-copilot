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

  return (
    <section aria-labelledby="latency-heading" className="flex min-w-0 flex-col gap-4">
      <h2 id="latency-heading" className="text-balance text-sm font-medium text-foreground">
        Latency
      </h2>
      {rows.length === 0 ? (
        <p className="text-sm leading-6 text-muted-foreground">
          No latency was measured for this session.
        </p>
      ) : (
        <>
          <ul aria-label="Legend" className="flex list-none flex-wrap gap-x-4 gap-y-1 p-0">
            {stageLabels.map(([key, label]) => (
              <li key={key} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span aria-hidden className={`size-2 rounded-xs ${STAGE_COLOR[key]}`} />
                {label}
              </li>
            ))}
          </ul>
          <ol aria-label="Latency by turn" className="flex min-w-0 list-none flex-col gap-4 p-0">
            {rows.map((row) => {
              const detail = row.stages
                .map((stage) => `${stage.label} ${formatMs(stage.ms)}`)
                .join(", ");
              return (
                <li key={row.id} className="flex min-w-0 flex-col gap-1.5">
                  <p className="flex justify-between gap-4 text-sm text-foreground">
                    <span className="[overflow-wrap:anywhere]">{row.name}</span>
                    <span className="tabular-nums text-muted-foreground">
                      {formatMs(row.total)}
                    </span>
                  </p>
                  <div
                    role="img"
                    aria-label={detail}
                    className="flex h-2 w-full gap-px overflow-hidden rounded-sm bg-muted"
                  >
                    {row.stages.map((stage) => (
                      <div
                        key={stage.key}
                        className={`h-full min-w-0.5 ${STAGE_COLOR[stage.key]}`}
                        style={{ width: `${(stage.ms / widest) * 100}%` }}
                      />
                    ))}
                  </div>
                  <p className="text-xs leading-5 text-muted-foreground tabular-nums">{detail}</p>
                </li>
              );
            })}
          </ol>
        </>
      )}
    </section>
  );
}
