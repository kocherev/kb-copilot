"use client";

import Link from "next/link";
import { useLayoutEffect, useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { apiPath, errorDetail, readJson } from "@/lib/api";
import {
  emptyDraft,
  isProduct,
  type Product,
  type ProductDraft,
} from "@/lib/product";

const linkClass =
  "underline underline-offset-4 [overflow-wrap:anywhere] focus-visible:[outline:var(--hui-focus-ring)] focus-visible:outline-offset-[var(--hui-focus-ring-offset-accent)]";

const fields: {
  key: keyof ProductDraft;
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
];

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
  initial?: ProductDraft;
  submitLabel: string;
  formLabel: string;
  onSaved?: (product: Product) => void;
}) {
  const [draft, setDraft] = useState<ProductDraft>({
    name: initial.name,
    description: initial.description,
    tone: initial.tone,
    refusal_rules: initial.refusal_rules,
  });
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

  function update(key: keyof ProductDraft, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setSaved(false);
    try {
      const response = await fetch(
        apiPath(apiUrl, productId ? `/products/${productId}` : "/products"),
        {
          method: productId ? "PUT" : "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(draft),
        },
      );
      const body = await readJson(response);
      if (!response.ok || !isProduct(body)) {
        setError(errorDetail(body, "Could not save the product."));
        return;
      }
      setDraft({
        name: body.name,
        description: body.description,
        tone: body.tone,
        refusal_rules: body.refusal_rules,
      });
      setCreated(body);
      setSaved(true);
      resetAfterHide.current = productId === undefined;
      onSaved?.(body);
    } catch {
      setError("Could not save the product.");
    } finally {
      setPending(false);
    }
  }

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
