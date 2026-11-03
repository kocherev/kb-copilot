import { letterbox, type Size } from "@/lib/letterbox";
import type { HudPoint } from "@/lib/protocol";

// The highlight is placed on the picture itself. A letterboxed video leaves
// bars inside its container, and the agent's coordinates are fractions of the
// picture, not of the container.
export function ScreenHud({
  thinking,
  point,
  container,
  video,
}: {
  thinking: boolean;
  point: HudPoint | null;
  container: Size;
  video: Size;
}) {
  const frame = letterbox(container, video);
  return (
    <div className="pointer-events-none absolute inset-0">
      <div role="status" className="absolute top-3 left-3">
        {thinking ? (
          <p className="rounded-full bg-[var(--hui-color-background-neutral-emphasis)] px-3 py-1 text-xs text-[var(--hui-color-foreground-base-emphasis)]">
            Thinking
          </p>
        ) : null}
      </div>
      {point ? (
        <div
          data-testid="hud-frame"
          className="absolute"
          style={{
            left: frame.left,
            top: frame.top,
            width: frame.width,
            height: frame.height,
          }}
        >
          <div
            className="absolute motion-safe:transition-[left,top] motion-safe:duration-200 motion-safe:ease-out"
            style={{ left: `${point.x * 100}%`, top: `${point.y * 100}%` }}
          >
            <div className="size-11 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[var(--hui-color-border-accent-emphasis)] bg-[color-mix(in_oklch,var(--hui-color-background-accent-emphasis)_24%,transparent)]" />
            <p className="max-w-40 -translate-x-1/2 rounded-md bg-[var(--hui-color-background-neutral-emphasis)] px-2 py-1 text-center text-xs leading-4 text-[var(--hui-color-foreground-base-emphasis)] [overflow-wrap:anywhere]">
              {point.label}
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
