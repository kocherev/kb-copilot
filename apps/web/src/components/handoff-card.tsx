"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { browserApi, errorDetail, type ApiClient, type Escalation } from "@/lib/api/client";
import type { EscalationProposal } from "@/lib/protocol";

type Outcome = { data?: Escalation; error?: unknown };

export function HandoffCard({
  apiUrl,
  proposal,
}: {
  apiUrl: string;
  proposal: EscalationProposal;
}) {
  const [result, setResult] = useState<Escalation | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const path = { params: { path: { escalation_id: proposal.id } } };

  async function run(send: (api: ApiClient) => Promise<Outcome>, fallback: string) {
    setPending(true);
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
      setPending(false);
    }
  }

  if (result?.status === "created") {
    return (
      <p role="status" className="text-pretty text-sm leading-6 text-foreground">
        Ticket {result.issue_identifier} created.{" "}
        {result.issue_url ? (
          <a
            href={result.issue_url}
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-4"
          >
            Open in Linear
          </a>
        ) : null}
      </p>
    );
  }
  if (result?.status === "dismissed") {
    return (
      <p role="status" className="text-pretty text-sm leading-6 text-muted-foreground">
        Ticket dismissed.
      </p>
    );
  }
  return (
    <section
      aria-label="Proposed ticket"
      className="flex min-w-0 flex-col gap-3 rounded-md border border-border p-4"
    >
      <p className="text-pretty text-sm leading-6 text-muted-foreground">
        The agent proposes this Linear ticket. Nothing is created until you approve it.
      </p>
      <h3 className="text-sm font-medium text-foreground [overflow-wrap:anywhere]">
        {proposal.title}
      </h3>
      <p className="max-h-48 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-muted-foreground [overflow-wrap:anywhere]">
        {proposal.body}
      </p>
      {error ? (
        <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
          {error}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-3">
        <Button
          type="button"
          disabled={pending}
          onClick={() =>
            void run((api) => api.POST("/escalations/{escalation_id}/approve", path), "Could not create the ticket.")
          }
        >
          Approve ticket
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={pending}
          onClick={() =>
            void run((api) => api.POST("/escalations/{escalation_id}/dismiss", path), "Could not dismiss the ticket.")
          }
        >
          Dismiss
        </Button>
      </div>
    </section>
  );
}
