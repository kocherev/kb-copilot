"use client";

import { ArrowLeft, Mic, MonitorUp, MousePointerClick, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";

import { SessionRoom } from "@/components/session-room";
import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/inline-error";
import { PageHeader } from "@/components/ui/page-header";
import { Spinner } from "@/components/ui/spinner";
import { Surface } from "@/components/ui/surface";
import { browserApi, type SessionGrant } from "@/lib/api/client";
import { sessionLoad } from "@/lib/session";

type MicAccess = "granted" | "denied" | "prompt" | "unknown";

// Reads the microphone permission without asking for it, so the check page
// can warn about a blocked microphone before the user joins.
function useMicAccess(): MicAccess {
  const [access, setAccess] = useState<MicAccess>("unknown");
  useEffect(() => {
    let status: PermissionStatus | null = null;
    const update = () => setAccess(status?.state ?? "unknown");
    navigator.permissions
      ?.query({ name: "microphone" as PermissionName })
      .then((found) => {
        status = found;
        update();
        found.addEventListener("change", update);
      })
      .catch(() => {});
    return () => status?.removeEventListener("change", update);
  }, []);
  return access;
}

const noSubscription = () => () => {};

// Phones and some tablets cannot share a screen from the browser.
function useCanShareScreen(): boolean {
  return useSyncExternalStore(
    noSubscription,
    () => typeof navigator.mediaDevices?.getDisplayMedia === "function",
    () => true,
  );
}

function Check({
  icon: Icon,
  title,
  tone = "neutral",
  children,
}: {
  icon: LucideIcon;
  title: string;
  tone?: "neutral" | "warning";
  children: ReactNode;
}) {
  return (
    <li className="flex min-w-0 gap-3">
      <span
        className={`grid size-9 shrink-0 place-items-center rounded-full ${tone === "warning" ? "bg-warning-soft text-warning" : "bg-primary-soft text-primary-soft-foreground"}`}
      >
        <Icon aria-hidden className="size-4" />
      </span>
      <div className="flex min-w-0 flex-col gap-0.5 pt-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p
          className={`text-meta text-pretty ${tone === "warning" ? "text-warning" : "text-muted-foreground"}`}
        >
          {children}
        </p>
      </div>
    </li>
  );
}

export function SessionStart({
  apiUrl,
  productId,
  productName,
  agentName,
}: {
  apiUrl: string;
  productId: string;
  productName: string;
  agentName: string;
}) {
  const [session, setSession] = useState<SessionGrant | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const mic = useMicAccess();
  const canShare = useCanShareScreen();

  async function start() {
    setPending(true);
    setError(null);
    try {
      const { data, error, response } = await browserApi(apiUrl).POST("/sessions", {
        body: { product_id: productId },
      });
      const loaded = sessionLoad(response.status, data, error);
      if (loaded.status === "error") {
        setError(loaded.message);
        return;
      }
      setSession(loaded.session);
    } catch {
      setError("Could not start the session. Check that the API is running, then try again.");
    } finally {
      setPending(false);
    }
  }

  const back = { href: `/products/${productId}`, label: `Back to ${productName}` };

  if (session) {
    return (
      <main className="mx-auto flex w-full max-w-[1080px] min-w-0 flex-col gap-5 overflow-x-clip px-4 pt-5 pb-28 animate-enter sm:px-8 lg:pb-10">
        <header className="flex min-w-0 flex-col gap-1">
          <Link
            href={back.href}
            className="-ml-1 flex w-fit max-w-full items-center gap-1 rounded-control px-1 py-0.5 text-meta text-muted-foreground transition-colors duration-150 ease-out outline-none hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
          >
            <ArrowLeft aria-hidden className="size-3.5 shrink-0" />
            <span className="truncate">{back.label}</span>
          </Link>
          <h1 className="font-display text-xl/tight text-balance text-foreground [overflow-wrap:anywhere] sm:text-title">
            {productName}
          </h1>
        </header>
        <SessionRoom
          url={session.url}
          token={session.token}
          room={session.room}
          apiUrl={apiUrl}
          agentName={agentName}
          onRestart={() => setSession(null)}
        />
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-[640px] min-w-0 flex-col gap-8 overflow-x-clip px-4 py-8 sm:px-8 sm:py-12">
      <PageHeader
        back={back}
        title={productName}
        description={`Talk to ${agentName} about what is on your screen. ${agentName} answers by voice from your docs.`}
      />
      <Surface className="flex flex-col gap-6 sm:p-6">
        <div className="flex flex-col gap-1">
          <h2 className="text-heading text-foreground">Before you join</h2>
          <p className="text-meta text-pretty text-muted-foreground">
            Your browser asks for each of these when you join.
          </p>
        </div>
        <ul className="flex list-none flex-col gap-4 p-0">
          <Check
            icon={Mic}
            title="Microphone"
            tone={mic === "denied" ? "warning" : "neutral"}
          >
            {mic === "denied"
              ? `Your browser blocks the microphone. Allow it in the site settings so ${agentName} can hear you.`
              : `${agentName} listens while you talk. You can mute at any time.`}
          </Check>
          <Check icon={MonitorUp} title="Screen" tone={canShare ? "neutral" : "warning"}>
            {canShare
              ? `Pick a window or a whole screen. ${agentName} sees it and points at what to click.`
              : `This browser can't share a screen. Join from a desktop browser so ${agentName} can see it.`}
          </Check>
          <Check icon={MousePointerClick} title="Your Mac (optional)">
            {agentName} can click for you once you connect your Mac, and asks before every
            step.
          </Check>
        </ul>
        {error ? <InlineError>{error}</InlineError> : null}
        <Button
          type="button"
          size="lg"
          disabled={pending}
          className="w-full sm:w-fit"
          onClick={() => void start()}
        >
          {pending ? <Spinner /> : null}
          {pending ? "Joining…" : "Join session"}
        </Button>
      </Surface>
    </main>
  );
}
