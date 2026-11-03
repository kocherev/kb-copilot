"use client";

import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import type { ActionProposal, Decision } from "@/lib/protocol";

// One step the agent wants to take on the user's Mac. Nothing runs until the
// user allows it here. Escape stops the task.
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
      className="flex min-w-0 flex-col gap-3 rounded-md border border-border p-4 outline-none focus-visible:[outline:var(--hui-focus-ring)]"
    >
      <p role="status" className="text-pretty text-sm leading-6 text-muted-foreground">
        {proposal.needsApproval
          ? `${agentName} wants to do this on your Mac. Nothing happens until you choose.`
          : `${agentName} is doing this on your Mac.`}
      </p>
      <h3 className="text-sm font-medium text-foreground [overflow-wrap:anywhere]">
        {proposal.description}
      </h3>
      {proposal.warning ? (
        <p role="alert" className="text-pretty text-sm leading-6 text-destructive [overflow-wrap:anywhere]">
          Check before you allow it: {proposal.warning}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-3">
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
        <Button type="button" variant="destructive-outline" onClick={() => onDecide("stop")}>
          Stop
        </Button>
      </div>
    </section>
  );
}
