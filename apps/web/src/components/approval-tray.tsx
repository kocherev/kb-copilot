"use client";

import { MousePointerClick, TriangleAlert } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import type { ActionProposal, Decision } from "@/lib/protocol";

// One step the agent wants to take on the user's Mac. Nothing runs until the
// user allows it here. Escape stops the task. On phones it floats above the
// docked controls so it is never below the fold.
export function ApprovalTray({
  agentName,
  proposal,
  onDecide,
}: {
  agentName: string;
  proposal: ActionProposal;
  onDecide: (decision: Decision) => void;
}) {
  const tray = useRef<HTMLElement>(null);
  // Focus lands on the tray, not on a button, so a stray Enter allows nothing.
  useEffect(() => {
    if (proposal.needsApproval) {
      tray.current?.focus();
    }
  }, [proposal.id, proposal.needsApproval]);
  return (
    <section
      ref={tray}
      tabIndex={-1}
      aria-label="Action approval"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          onDecide("stop");
        }
      }}
      className="fixed inset-x-3 bottom-[calc(5.25rem+env(safe-area-inset-bottom))] z-(--z-overlay) flex min-w-0 flex-col gap-3 rounded-card border border-transparent bg-surface p-4 shadow-float ring-1 ring-primary/30 outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring lg:static"
    >
      <div className="flex min-w-0 items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-primary-soft text-primary-soft-foreground">
          <MousePointerClick aria-hidden className="size-4" />
        </span>
        <div className="flex min-w-0 flex-col gap-0.5">
          <p role="status" className="text-meta text-pretty text-muted-foreground">
            {proposal.needsApproval
              ? `${agentName} wants to do this on your Mac. Nothing happens until you choose.`
              : `${agentName} is doing this on your Mac.`}
          </p>
          <h3 className="text-heading text-balance text-foreground [overflow-wrap:anywhere]">
            {proposal.description}
          </h3>
        </div>
      </div>
      {proposal.warning ? (
        <p
          role="alert"
          className="flex min-w-0 items-start gap-2 rounded-control bg-destructive-soft px-3 py-2 text-sm text-pretty text-destructive [overflow-wrap:anywhere]"
        >
          <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
          <span>Check before you allow it: {proposal.warning}</span>
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        {proposal.needsApproval ? (
          <>
            <Button type="button" onClick={() => onDecide("once")}>
              Allow once
            </Button>
            <Button type="button" variant="outline" onClick={() => onDecide("task")}>
              Allow for this task
            </Button>
          </>
        ) : null}
        <Button
          type="button"
          variant="destructive-outline"
          className="sm:ml-auto"
          onClick={() => onDecide("stop")}
        >
          Stop
        </Button>
      </div>
      <p className="text-meta text-subtle-foreground max-lg:hidden">
        Press <kbd className="rounded border border-border px-1 font-mono text-xs">Esc</kbd> to stop.
      </p>
    </section>
  );
}
