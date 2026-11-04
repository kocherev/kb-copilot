"use client";

import { UserRound } from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
  type RefObject,
} from "react";
import { createPortal } from "react-dom";

import { Arrow } from "@/components/agent-cursor/agent-cursor";
import { ScreenGlow } from "@/components/screen-glow";
import { cropAround, type Size } from "@/lib/letterbox";
import type { HudPoint } from "@/lib/protocol";

// Document Picture-in-Picture, Chromium 116 and later. TypeScript's DOM types
// do not have it yet.
type PictureInPicture = {
  requestWindow: (options: { width: number; height: number }) => Promise<Window>;
};

function pictureInPicture(): PictureInPicture | undefined {
  return (window as Window & { documentPictureInPicture?: PictureInPicture })
    .documentPictureInPicture;
}

const WINDOW = { width: 320, height: 200 };
const CROP_VIEW = { width: 128, height: 80 };
const ZOOM = 3;

function copyStyles(target: Document) {
  // The floating document is about:blank, so relative font and image URLs in
  // the copied rules need the page's address as their base.
  const base = target.createElement("base");
  base.href = document.baseURI;
  target.head.append(base);
  for (const sheet of Array.from(document.styleSheets)) {
    try {
      const style = target.createElement("style");
      style.textContent = Array.from(sheet.cssRules, (rule) => rule.cssText).join("\n");
      target.head.append(style);
    } catch {
      // A cross-origin sheet hides its rules, so link it instead.
      if (sheet.href) {
        const link = target.createElement("link");
        link.rel = "stylesheet";
        link.href = sheet.href;
        target.head.append(link);
      }
    }
  }
}

// The theme and font variables live on <html> and <body>.
function mirrorRoot(target: Document) {
  target.documentElement.className = document.documentElement.className;
  Object.assign(target.documentElement.dataset, document.documentElement.dataset);
  target.body.className = document.body.className;
}

const noSubscription = () => () => {};

// A small always-on-top window that keeps the agent visible while the user
// works in other apps. Closed and unavailable while active is false.
export function usePresenceWindow(active: boolean, title: string) {
  const supported = useSyncExternalStore(
    noSubscription,
    () => pictureInPicture() !== undefined,
    () => false,
  );
  const [opened, setOpened] = useState<Window | null>(null);

  useEffect(() => {
    if (!opened || !active) {
      return;
    }
    const watch = new MutationObserver(() => mirrorRoot(opened.document));
    watch.observe(document.documentElement, { attributes: true });
    return () => {
      watch.disconnect();
      opened.close();
    };
  }, [opened, active]);

  async function open() {
    const api = pictureInPicture();
    if (!api || !active || opened) {
      return;
    }
    const next = await api.requestWindow(WINDOW);
    next.document.title = title;
    copyStyles(next.document);
    mirrorRoot(next.document);
    next.addEventListener("pagehide", () => setOpened(null), { once: true });
    setOpened(next);
  }

  return {
    supported,
    target: active ? opened : null,
    open,
    close: () => opened?.close(),
  };
}

function instruction(point: HudPoint): string {
  switch (point.kind) {
    case "about-to-click":
      return "Waiting for your OK";
    case "clicking":
      return "Doing it now";
    default:
      return "Look at";
  }
}

// A zoomed still of the shared screen around the point, redrawn when the
// point moves. The arrow sits where the point lands inside the crop.
function PointCrop({
  point,
  video,
  source,
}: {
  point: HudPoint;
  video: Size;
  source: RefObject<HTMLVideoElement | null>;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const crop = cropAround(point, video, CROP_VIEW, ZOOM);
  useEffect(() => {
    const frame = source.current;
    const context = canvas.current?.getContext("2d");
    if (!frame || !context || frame.videoWidth === 0 || video.width === 0) {
      return;
    }
    // The publication size and the element's own size can differ.
    const scale = frame.videoWidth / video.width;
    context.drawImage(
      frame,
      crop.left * scale,
      crop.top * scale,
      crop.width * scale,
      crop.height * scale,
      0,
      0,
      context.canvas.width,
      context.canvas.height,
    );
  }, [source, video.width, crop.left, crop.top, crop.width, crop.height]);
  return (
    <div
      aria-hidden
      className="relative shrink-0 overflow-hidden rounded-lg bg-surface-sunken shadow-ring"
      style={CROP_VIEW}
    >
      <canvas
        ref={canvas}
        width={CROP_VIEW.width * 2}
        height={CROP_VIEW.height * 2}
        className="size-full"
      />
      <span
        className="absolute"
        style={{ left: `${crop.cursor.x * 100}%`, top: `${crop.cursor.y * 100}%` }}
      >
        <Arrow />
      </span>
    </div>
  );
}

export function PresenceWindow({
  target,
  agentName,
  status,
  live,
  agentState,
  point,
  video,
  source,
  controls,
}: {
  target: Window;
  agentName: string;
  status: string;
  live: boolean;
  agentState: string;
  point: HudPoint | null;
  video: Size;
  source: RefObject<HTMLVideoElement | null>;
  controls: ReactNode;
}) {
  return createPortal(
    <main className="flex h-dvh min-w-0 flex-col gap-3 overflow-hidden bg-background p-4 text-foreground">
      <div className="flex min-w-0 items-center gap-3">
        <ScreenGlow watching={live} agentState={agentState}>
          <span className="grid size-9 shrink-0 place-items-center rounded-full bg-surface-sunken text-muted-foreground">
            <UserRound aria-hidden className="size-4" />
          </span>
        </ScreenGlow>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-sm font-medium">{agentName}</h1>
          <p role="status" aria-label="Agent" className="line-clamp-2 text-meta text-muted-foreground">
            {status}
          </p>
        </div>
        <div role="group" aria-label="Session controls" className="flex shrink-0 items-center gap-1">
          {controls}
        </div>
      </div>
      {point && live ? (
        <div className="flex min-h-0 min-w-0 items-center gap-3">
          <PointCrop point={point} video={video} source={source} />
          <p role="status" aria-label="Pointer" className="min-w-0 text-sm [overflow-wrap:anywhere]">
            <span className="block text-meta text-muted-foreground">{instruction(point)}</span>
            <span className="line-clamp-3 font-medium">{point.label}</span>
          </p>
        </div>
      ) : (
        <p className="text-meta text-pretty text-muted-foreground">
          When {agentName} points at something on your screen, it shows here.
        </p>
      )}
    </main>,
    target.document.body,
  );
}
