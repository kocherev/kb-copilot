"use client";

import { FileText } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PendingLabel } from "@/components/product-form";
import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/inline-error";
import { Input } from "@/components/ui/input";
import { authClient } from "@/lib/auth-client";
import { stagger } from "@/lib/motion";

type Mode = "sign-in" | "sign-up";

const copy: Record<
  Mode,
  {
    title: string;
    lede: string;
    submit: string;
    pending: string;
    failed: string;
    prompt: string;
    other: string;
    href: string;
  }
> = {
  "sign-in": {
    title: "Welcome back",
    lede: "Sign in to your products and sessions.",
    submit: "Sign in",
    pending: "Signing in…",
    failed: "Couldn’t sign in. Check your connection and try again.",
    prompt: "New here?",
    other: "Create an account",
    href: "/sign-up",
  },
  "sign-up": {
    title: "Create your account",
    lede: "Set up a product and talk to its agent in a few minutes.",
    submit: "Create account",
    pending: "Creating account…",
    failed: "Couldn’t create your account. Check your connection and try again.",
    prompt: "Already have an account?",
    other: "Sign in instead",
    href: "/sign-in",
  },
};

const linkClass =
  "rounded-sm font-medium text-link underline decoration-foreground/30 underline-offset-4 outline-none hover:decoration-current focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring";

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const text = copy[mode];

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) {
      return;
    }
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    setPending(true);
    setError(null);
    try {
      const result =
        mode === "sign-up"
          ? await authClient.signUp.email({
              name: String(form.get("name") ?? ""),
              email,
              password,
            })
          : await authClient.signIn.email({ email, password });
      if (result.error) {
        setError(result.error.message ?? text.failed);
        return;
      }
      router.replace("/");
      router.refresh();
    } catch {
      setError(text.failed);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="grid min-h-dvh w-full min-w-0 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <Hero />
      <div className="flex min-w-0 flex-col px-4 py-12 sm:justify-center sm:px-8 lg:py-16">
        <div className="mx-auto flex w-full max-w-sm min-w-0 flex-col gap-8">
          <p className="animate-enter text-meta text-pretty text-muted-foreground lg:hidden">
            {tagline}
          </p>
          <div className="flex min-w-0 animate-enter flex-col gap-2" style={stagger(1)}>
            <h1 className="font-display text-title text-balance text-foreground">{text.title}</h1>
            <p className="text-body text-pretty text-muted-foreground">{text.lede}</p>
          </div>
          <form
            aria-label={text.submit}
            aria-busy={pending}
            className="flex min-w-0 animate-enter flex-col gap-5"
            style={stagger(2)}
            onSubmit={onSubmit}
          >
            {mode === "sign-up" ? (
              <Field id="auth-name" name="name" label="Name" autoComplete="name" />
            ) : null}
            <Field
              id="auth-email"
              name="email"
              label="Email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
            />
            <Field
              id="auth-password"
              name="password"
              label="Password"
              type="password"
              autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
              minLength={8}
              hint={mode === "sign-up" ? "Use at least 8 characters." : undefined}
            />
            {error ? <InlineError>{error}</InlineError> : null}
            <Button type="submit" size="lg" aria-disabled={pending} className="mt-1 w-full">
              <PendingLabel pending={pending} label={text.submit} pendingLabel={text.pending} />
            </Button>
          </form>
          <p className="animate-enter text-sm text-muted-foreground" style={stagger(3)}>
            {text.prompt}{" "}
            <Link className={linkClass} href={text.href}>
              {text.other}
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}

const tagline = "A support agent that reads your docs and sees your screen.";


// What the product does, shown before anyone has an account. The exchange is
// an illustration, marked as one.
function Hero() {
  return (
    <section
      aria-label="About KB Copilot"
      className="hidden min-w-0 flex-col items-center justify-center overflow-hidden bg-surface-sunken px-12 py-16 lg:flex xl:px-16"
    >
      <div className="flex w-full max-w-[30rem] min-w-0 flex-col gap-10">
        <div className="flex animate-enter flex-col gap-4">
          <p className="font-display text-display text-balance text-foreground">
            {tagline}
          </p>
          <p className="text-body text-pretty text-muted-foreground">
            Upload a product’s help pages, then start a voice session. The agent answers out loud,
            points at what to click and shows the page behind each answer.
          </p>
        </div>
        <figure
          className="flex animate-enter flex-col gap-3 rounded-card border border-transparent bg-surface p-4 shadow-soft"
          style={stagger(2)}
        >
          <figcaption className="text-overline text-subtle-foreground uppercase">Example</figcaption>
          <p className="max-w-[85%] self-end rounded-[14px] rounded-br-md bg-surface-sunken px-3.5 py-2 text-sm text-foreground">
            Where do I change the billing email?
          </p>
          <div className="flex max-w-[92%] flex-col gap-2 self-start">
            <p className="rounded-[14px] rounded-bl-md bg-primary-soft px-3.5 py-2 text-sm text-primary-soft-foreground">
              Open Settings, then Billing. I’ve pointed at the field on your screen.
            </p>
            <p className="flex w-fit items-center gap-1.5 rounded-full bg-surface px-2.5 py-1 text-meta text-muted-foreground shadow-ring">
              <FileText aria-hidden className="size-3.5" />
              billing/update-email.md
            </p>
          </div>
        </figure>
      </div>
    </section>
  );
}

function Field({
  id,
  label,
  hint,
  ...props
}: { id: string; label: string; hint?: string } & React.ComponentProps<"input">) {
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <label htmlFor={id} className="text-sm font-medium text-foreground">
        {label}
      </label>
      <Input id={id} required aria-describedby={hintId} {...props} />
      {hint ? (
        <p id={hintId} className="text-meta text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
