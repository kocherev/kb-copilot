"use client";

import Link from "next/link";
import { useLayoutEffect, useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  browserApi,
  errorDetail,
  type Product,
  type ProductWrite,
} from "@/lib/api/client";
import { emptyDraft, voices } from "@/lib/product";

const linkClass =
  "underline underline-offset-4 [overflow-wrap:anywhere] focus-visible:[outline:var(--hui-focus-ring)] focus-visible:outline-offset-[var(--hui-focus-ring-offset-accent)]";

const fields: {
  key: keyof ProductWrite;
  label: string;
  hint?: string;
  multiline: boolean;
  maxLength: number;
  rows?: number;
}[] = [
  { key: "name", label: "Name", multiline: false, maxLength: 120 },
  {
    key: "description",
    label: "Description",
    hint: "One paragraph.",
    multiline: true,
    maxLength: 2000,
    rows: 3,
  },
  { key: "tone", label: "Tone", multiline: false, maxLength: 200 },
  {
    key: "refusal_rules",
    label: "Refusal rules",
    hint: "What the agent must not do.",
    multiline: true,
    maxLength: 4000,
    rows: 4,
  },
  {
    key: "agent_name",
    label: "Agent name",
    hint: "What the agent calls itself.",
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
  const [created, setCreated] = useState<Product | null>(null);
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
      setCreated(null);
    };
  }, []);

  function update(key: keyof ProductWrite, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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
        setError(errorDetail(error, "Could not save the product."));
        return;
      }
      setDraft(writable(product));
      setCreated(product);
      setSaved(true);
      resetAfterHide.current = productId === undefined;
      onSaved?.(product);
    } catch {
      setError("Could not save the product.");
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
              <p id={hintId} className="text-pretty text-sm leading-6 text-muted-foreground">
                {field.hint}
              </p>
            ) : null}
            {field.multiline ? (
              <Textarea
                id={id}
                name={field.key}
                value={draft[field.key]}
                rows={field.rows}
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
      {error ? (
        <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
          {error}
        </p>
      ) : null}
      {saved ? (
        <p role="status" className="text-sm text-foreground">
          Saved
        </p>
      ) : null}
      {!productId && created ? (
        <Link className={linkClass} href={`/products/${created.id}`}>
          Open {created.name}
        </Link>
      ) : null}
      <Button type="submit" disabled={pending}>
        {submitLabel}
      </Button>
    </form>
  );
}
