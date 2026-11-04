"use client";

import { LifeBuoy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/inline-error";
import { InlineStatus } from "@/components/ui/inline-status";
import { Spinner } from "@/components/ui/spinner";
import { browserApi, errorDetail, type ApiClient, type Escalation } from "@/lib/api/client";
import type { EscalationProposal } from "@/lib/protocol";

type Outcome = { data?: Escalation; error?: unknown };

export function HandoffCard({
  apiUrl,
  agentName,
  proposal,
}: {
  apiUrl: string;
  agentName: string;
  proposal: EscalationProposal;
}) {
  const [result, setResult] = useState<Escalation | null>(null);
  const [pending, setPending] = useState<"approve" | "dismiss" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const path = { params: { path: { escalation_id: proposal.id } } };

  async function run(
    action: "approve" | "dismiss",
    send: (api: ApiClient) => Promise<Outcome>,
    fallback: string,
  ) {
    setPending(action);
    setError(null);
    try {
      const outcome = await send(browserApi(apiUrl));
      if (outcome.data) {
        setResult(outcome.data);
      } else {
        setError(errorDetail(outcome.error, fallback));
      }
    } catch {
      setError(fallback);
    } finally {
      setPending(null);
    }
  }

  if (result?.status === "created") {
    return (
      <InlineStatus tone="success" className="animate-enter">
        Ticket {result.issue_identifier} created.{" "}
        {result.issue_url ? (
          <a
            href={result.issue_url}
            target="_blank"
            rel="noreferrer"
            className="text-link underline decoration-foreground/30 underline-offset-4 hover:decoration-current"
          >
            Open in Linear
          </a>
        ) : null}
      </InlineStatus>
    );
  }
  if (result?.status === "dismissed") {
    return <InlineStatus className="animate-enter">Ticket dismissed.</InlineStatus>;
  }
  return (
    <section
      aria-label="Proposed ticket"
      className="flex min-w-0 flex-col gap-3 rounded-card border border-transparent bg-surface p-4 shadow-float ring-1 ring-primary/30 animate-enter"
    >
      <div className="flex min-w-0 items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-primary-soft text-primary-soft-foreground">
          <LifeBuoy aria-hidden className="size-4" />
        </span>
        <div className="flex min-w-0 flex-col gap-0.5">
          <p className="text-meta text-pretty text-muted-foreground">
            {agentName} proposes this Linear ticket. Nothing is created until you approve it.
          </p>
          <h3 className="text-heading text-balance text-foreground [overflow-wrap:anywhere]">
            {proposal.title}
          </h3>
        </div>
      </div>
      <p className="max-h-48 overflow-y-auto overscroll-contain rounded-control bg-surface-sunken px-3 py-2.5 text-meta whitespace-pre-wrap text-muted-foreground [overflow-wrap:anywhere]">
        {proposal.body}
      </p>
      {error ? <InlineError>{error}</InlineError> : null}
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          disabled={pending !== null}
          onClick={() =>
            void run(
              "approve",
              (api) => api.POST("/escalations/{escalation_id}/approve", path),
              "Could not create the ticket. Try again.",
            )
          }
        >
          {pending === "approve" ? <Spinner /> : null}
          {pending === "approve" ? "Creating ticket…" : "Approve ticket"}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={pending !== null}
          onClick={() =>
            void run(
              "dismiss",
              (api) => api.POST("/escalations/{escalation_id}/dismiss", path),
              "Could not dismiss the ticket. Try again.",
            )
          }
        >
          {pending === "dismiss" ? <Spinner /> : null}
          {pending === "dismiss" ? "Dismissing…" : "Dismiss"}
        </Button>
      </div>
    </section>
  );
}
