"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authClient } from "@/lib/auth-client";

const linkClass =
  "text-sm underline underline-offset-4 focus-visible:[outline:var(--hui-focus-ring)] focus-visible:outline-offset-[var(--hui-focus-ring-offset-accent)]";

type Mode = "sign-in" | "sign-up";

const copy: Record<Mode, { title: string; submit: string; other: string; href: string }> = {
  "sign-in": {
    title: "Sign in",
    submit: "Sign in",
    other: "Create an account",
    href: "/sign-up",
  },
  "sign-up": {
    title: "Create an account",
    submit: "Create account",
    other: "Sign in instead",
    href: "/sign-in",
  },
};

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const text = copy[mode];

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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
        setError(result.error.message ?? "Could not sign in.");
        return;
      }
      router.replace("/");
      router.refresh();
    } catch {
      setError("Could not sign in.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-sm min-w-0 flex-col gap-8 px-6 py-16">
      <h1 className="text-balance text-2xl font-medium tracking-tight text-foreground">
        {text.title}
      </h1>
      <form
        aria-label={text.title}
        aria-busy={pending}
        className="flex min-w-0 flex-col gap-5"
        onSubmit={onSubmit}
      >
        {mode === "sign-up" ? (
          <Field id="auth-name" name="name" label="Name" autoComplete="name" />
        ) : null}
        <Field id="auth-email" name="email" label="Email" type="email" autoComplete="email" />
        <Field
          id="auth-password"
          name="password"
          label="Password"
          type="password"
          autoComplete={mode === "sign-up" ? "new-password" : "current-password"}
          minLength={8}
        />
        {error ? (
          <p role="alert" className="text-pretty text-sm leading-6 text-destructive">
            {error}
          </p>
        ) : null}
        <Button type="submit" disabled={pending}>
          {text.submit}
        </Button>
      </form>
      <Link className={linkClass} href={text.href}>
        {text.other}
      </Link>
    </main>
  );
}

function Field({
  id,
  label,
  ...props
}: { id: string; label: string } & React.ComponentProps<"input">) {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <label htmlFor={id} className="text-sm font-medium text-foreground">
        {label}
      </label>
      <Input id={id} required {...props} />
    </div>
  );
}
