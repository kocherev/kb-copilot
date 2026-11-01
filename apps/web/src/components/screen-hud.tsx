import type { HudPoint } from "@/lib/session";

export function ScreenHud({
  thinking,
  point,
}: {
  thinking: boolean;
  point: HudPoint | null;
}) {
  return (
    <div className="pointer-events-none absolute inset-0">
      <p
        role="status"
        className={`absolute top-3 left-3 rounded-full bg-[var(--hui-color-background-neutral-emphasis)] px-3 py-1 text-xs text-[var(--hui-color-foreground-base-emphasis)] motion-safe:transition-opacity motion-safe:duration-200 motion-safe:ease-out ${thinking ? "opacity-100" : "opacity-0"}`}
      >
        Thinking
      </p>
      {point ? (
        <div
          className="absolute motion-safe:transition-[left,top] motion-safe:duration-200 motion-safe:ease-out"
          style={{ left: `${point.x * 100}%`, top: `${point.y * 100}%` }}
        >
          <div className="size-11 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[var(--hui-color-border-accent-emphasis)] bg-[color-mix(in_oklch,var(--hui-color-background-accent-emphasis)_24%,transparent)]" />
          <p className="max-w-40 -translate-x-1/2 rounded-md bg-[var(--hui-color-background-neutral-emphasis)] px-2 py-1 text-center text-xs leading-4 text-[var(--hui-color-foreground-base-emphasis)] [overflow-wrap:anywhere]">
            {point.label}
          </p>
        </div>
      ) : null}
    </div>
  );
}
