"use client";

import { useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/inline-error";
import { InlineStatus } from "@/components/ui/inline-status";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import {
  browserApi,
  errorDetail,
  type Product,
  type ProductWrite,
} from "@/lib/api/client";
import { emptyDraft, voices } from "@/lib/product";

// A button label that swaps to a spinner and a pending label without the
// button changing width: both labels share one grid cell and the wider one
// sizes it.
export function PendingLabel({
  pending,
  label,
  pendingLabel,
}: {
  pending: boolean;
  label: ReactNode;
  pendingLabel: string;
}) {
  return (
    <span className="grid place-items-center">
      <span
        aria-hidden={pending}
        className={`col-start-1 row-start-1 inline-flex items-center gap-2 ${pending ? "invisible" : ""}`}
      >
        {label}
      </span>
      <span
        aria-hidden={!pending}
        className={`col-start-1 row-start-1 inline-flex items-center gap-2 ${pending ? "" : "invisible"}`}
      >
        <Spinner />
        {pendingLabel}
      </span>
    </span>
  );
}

const fields: {
  key: keyof ProductWrite;
  label: string;
  hint?: string;
  placeholder: string;
  multiline: boolean;
  maxLength: number;
  rows?: number;
}[] = [
  { key: "name", label: "Name", placeholder: "Northstar Desk", multiline: false, maxLength: 120 },
  {
    key: "description",
    label: "Description",
    hint: "One paragraph about what the product does.",
    placeholder: "Northstar Desk is a help desk for small support teams.",
    multiline: true,
    maxLength: 2000,
    rows: 3,
  },
  {
    key: "tone",
    label: "Tone",
    hint: "How the agent should sound.",
    placeholder: "calm and brief",
    multiline: false,
    maxLength: 200,
  },
  {
    key: "refusal_rules",
    label: "Refusal rules",
    hint: "What the agent must not do.",
    placeholder: "Don’t promise refunds or discounts.",
    multiline: true,
    maxLength: 4000,
    rows: 4,
  },
  {
    key: "agent_name",
    label: "Agent name",
    hint: "What the agent calls itself.",
    placeholder: "Shawn",
    multiline: false,
    maxLength: 40,
  },
];

function writable(source: ProductWrite): ProductWrite {
  const { name, description, tone, refusal_rules, agent_name, voice } = source;
  return { name, description, tone, refusal_rules, agent_name, voice };
}

export function ProductForm({
  apiUrl,
  productId,
  initial = emptyDraft,
  submitLabel,
  formLabel,
  onSaved,
}: {
  apiUrl: string;
  productId?: string;
  initial?: ProductWrite;
  submitLabel: string;
  formLabel: string;
  onSaved?: (product: Product) => void;
}) {
  const [draft, setDraft] = useState<ProductWrite>(writable(initial));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [pending, setPending] = useState(false);
  const resetAfterHide = useRef(false);

  useLayoutEffect(() => {
    return () => {
      if (!resetAfterHide.current) {
        return;
      }
      resetAfterHide.current = false;
      setDraft(emptyDraft);
      setError(null);
      setSaved(false);
    };
  }, []);

  function update(key: keyof ProductWrite, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) {
      return;
    }
    setPending(true);
    setError(null);
    setSaved(false);
    // The API keeps the description to one paragraph.
    const body = {
      ...draft,
      description: draft.description.replace(/\s*[\r\n]+\s*/g, " "),
    };
    try {
      const api = browserApi(apiUrl);
      const { data: product, error } = productId
        ? await api.PUT("/products/{product_id}", {
            params: { path: { product_id: productId } },
            body,
          })
        : await api.POST("/products", { body });
      if (product === undefined) {
        setError(errorDetail(error, "Couldn’t save the product. Check your connection and try again."));
        return;
      }
      setDraft(writable(product));
      setSaved(true);
      resetAfterHide.current = productId === undefined;
      onSaved?.(product);
    } catch {
      setError("Couldn’t save the product. Check your connection and try again.");
    } finally {
      setPending(false);
    }
  }

  const voiceId = `${formLabel}-voice`.replaceAll(" ", "-").toLowerCase();
  return (
    <form
      aria-label={formLabel}
      aria-busy={pending}
      className="flex min-w-0 flex-col gap-5"
      onSubmit={onSubmit}
    >
      {fields.map((field) => {
        const id = `${formLabel}-${field.key}`.replaceAll(" ", "-").toLowerCase();
        const hintId = field.hint ? `${id}-hint` : undefined;
        return (
          <div key={field.key} className="flex min-w-0 flex-col gap-2">
            <label htmlFor={id} className="text-sm font-medium text-foreground">
              {field.label}
            </label>
            {field.hint ? (
              <p id={hintId} className="-mt-1 text-meta text-pretty text-muted-foreground">
                {field.hint}
              </p>
            ) : null}
            {field.multiline ? (
              <Textarea
                id={id}
                name={field.key}
                value={draft[field.key]}
                rows={field.rows}
                placeholder={field.placeholder}
                maxLength={field.maxLength}
                aria-describedby={hintId}
                required
                onChange={(event) => update(field.key, event.target.value)}
              />
            ) : (
              <Input
                id={id}
                name={field.key}
                value={draft[field.key]}
                placeholder={field.placeholder}
                maxLength={field.maxLength}
                aria-describedby={hintId}
                required
                autoComplete="off"
                onChange={(event) => update(field.key, event.target.value)}
              />
            )}
          </div>
        );
      })}
      <div className="flex min-w-0 flex-col gap-2">
        <label htmlFor={voiceId} className="text-sm font-medium text-foreground">
          Voice
        </label>
        <Select
          id={voiceId}
          name="voice"
          value={draft.voice}
          onChange={(event) => {
            const voice = voices.find((item) => item.value === event.target.value);
            if (voice) {
              setDraft((current) => ({ ...current, voice: voice.value }));
              setSaved(false);
            }
          }}
        >
          {voices.map((voice) => (
            <option key={voice.value} value={voice.value}>
              {voice.value}, {voice.trait.toLowerCase()}
            </option>
          ))}
        </Select>
      </div>
      {error ? <InlineError>{error}</InlineError> : null}
      <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
        <Button type="submit" aria-disabled={pending}>
          <PendingLabel
            pending={pending}
            label={submitLabel}
            pendingLabel={productId ? "Saving…" : "Creating product…"}
          />
        </Button>
        <InlineStatus tone="success">{saved ? "Saved" : null}</InlineStatus>
      </div>
    </form>
  );
}
