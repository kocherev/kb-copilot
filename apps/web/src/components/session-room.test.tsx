import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { SessionRoom } from "@/components/session-room";
import { stubApi } from "@/test/api-stub";

type Item = {
  text: string;
  participantInfo: { identity: string };
  streamInfo: { id: string };
};
const live = vi.hoisted(() => ({
  transcriptions: [] as Item[],
  state: "connected",
  assistant: "listening",
  agentPresent: true,
  handlers: {} as Record<string, (message: { payload: Uint8Array }) => void>,
  disconnect: vi.fn(),
  dimensions: undefined as { width: number; height: number } | undefined,
}));

vi.mock("@livekit/components-react", () => ({
  LiveKitRoom: ({
    children,
    serverUrl,
    token,
    audio,
    video,
    screen: shareScreen,
    connect,
  }: {
    children?: React.ReactNode;
    serverUrl?: string;
    token?: string;
    audio?: boolean;
    video?: boolean;
    screen?: boolean;
    connect?: boolean;
  }) => (
    <div
      data-testid="room"
      data-url={serverUrl}
      data-token={token}
      data-audio={String(audio)}
      data-video={String(video)}
      data-screen={String(shareScreen)}
      data-connect={String(connect)}
    >
      {children}
    </div>
  ),
  RoomAudioRenderer: () => <div data-testid="agent-audio" />,
  VideoTrack: () => <div data-testid="shared-video" />,
  useConnectionState: () => live.state,
  useDataChannel: (
    topic: string,
    handler: (message: { payload: Uint8Array }) => void,
  ) => {
    live.handlers[topic] = handler;
  },
  useRoomContext: () => ({ disconnect: live.disconnect }),
  useTracks: () =>
    live.dimensions ? [{ publication: { dimensions: live.dimensions } }] : [],
  useTranscriptions: () => live.transcriptions,
  useVoiceAssistant: () => ({
    state: live.assistant,
    agent: live.agentPresent ? {} : undefined,
  }),
  TrackToggle: ({ "aria-label": label }: { "aria-label"?: string }) => (
    <button type="button">{label}</button>
  ),
}));

vi.mock("livekit-client", () => ({
  Track: { Source: { Microphone: "microphone", ScreenShare: "screen_share" } },
}));

class FakeResizeObserver {
  constructor(private callback: ResizeObserverCallback) {}
  observe() {
    this.callback(
      [{ contentRect: { width: 800, height: 450 } } as ResizeObserverEntry],
      this as unknown as ResizeObserver,
    );
  }
  disconnect() {}
  unobserve() {}
}

function stubMatchMedia(reducedMotion: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: reducedMotion && query.includes("prefers-reduced-motion"),
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  stubMatchMedia(false);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  live.transcriptions = [];
  live.state = "connected";
  live.assistant = "listening";
  live.agentPresent = true;
  live.handlers = {};
  live.dimensions = undefined;
  live.disconnect.mockReset();
});

function send(topic: string, body: unknown) {
  act(() => {
    live.handlers[topic]?.({
      payload: new TextEncoder().encode(JSON.stringify(body)),
    });
  });
}

function renderRoom(onRestart = () => {}) {
  render(
    <SessionRoom
      url="ws://localhost:7880"
      token="signed-token"
      apiUrl="http://localhost:8000"
      agentName="Mina"
      onRestart={onRestart}
    />,
  );
}

const agentLine = (id: string, text: string): Item => ({
  text,
  participantInfo: { identity: "agent-1" },
  streamInfo: { id },
});

test("the room joins with the token, mic and screen but no camera", () => {
  renderRoom();

  const room = screen.getByTestId("room");
  expect(room.getAttribute("data-url")).toBe("ws://localhost:7880");
  expect(room.getAttribute("data-token")).toBe("signed-token");
  expect(room.getAttribute("data-audio")).toBe("true");
  expect(room.getAttribute("data-video")).toBe("false");
  expect(room.getAttribute("data-screen")).toBe("true");
  expect(room.getAttribute("data-connect")).toBe("true");
  expect(screen.getByTestId("agent-audio")).toBeDefined();
  expect(screen.getByRole("button", { name: "Microphone" })).toBeDefined();
  expect(screen.getByRole("button", { name: "Screen share" })).toBeDefined();
  expect(screen.getByText("Share your screen so Mina can see it.")).toBeDefined();
});

test.each([
  ["connecting", "Connecting"],
  ["connected", "In the room"],
  ["reconnecting", "Connection lost. Reconnecting"],
  ["signalReconnecting", "Connection lost. Reconnecting"],
  ["disconnected", "Session ended"],
])("the %s state reads %s", (state, text) => {
  live.state = state;

  renderRoom();

  expect(screen.getByRole("status", { name: "Connection" }).textContent).toBe(text);
});

test("end session leaves the room, and an ended room offers a new one", () => {
  const onRestart = vi.fn();
  renderRoom(onRestart);

  fireEvent.click(screen.getByRole("button", { name: "End session" }));
  expect(live.disconnect).toHaveBeenCalledOnce();

  cleanup();
  live.state = "disconnected";
  renderRoom(onRestart);
  expect(screen.queryByRole("button", { name: "End session" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "New session" }));
  expect(onRestart).toHaveBeenCalledOnce();
});

test("the transcript is a polite log that shows citations from data messages", () => {
  live.transcriptions = [
    agentLine("a1", "Refunds take five business days."),
    agentLine("a2", "That is not in the docs."),
  ];
  renderRoom();
  expect(screen.queryByRole("list", { name: "Sources" })).toBeNull();

  send("citations", {
    message_id: "m1",
    text: "Refunds take  five business days.",
    passages: [
      {
        id: "p1",
        title: "Refund timing",
        source: "billing/refunds.md",
        anchor: "refund-timing",
        snippet: "Refunds reach the card in five business days.",
      },
    ],
  });

  const log = screen.getByRole("log");
  expect(log.getAttribute("aria-live")).toBe("polite");
  const sources = within(log).getByRole("list", { name: "Sources" });
  expect(within(sources).getByText(/Refund timing/)).toBeDefined();
  expect(within(sources).getByText("Refunds reach the card in five business days.")).toBeDefined();
  expect(within(log).getAllByRole("list", { name: "Sources" })).toHaveLength(1);
});

test("an agent error and a malformed message", () => {
  renderRoom();

  send("agent-error", { message: "The agent could not start (RuntimeError)." });
  send("citations", { nonsense: true });

  expect(screen.getByRole("alert").textContent).toBe(
    "The agent could not start (RuntimeError).",
  );
  expect(screen.queryByRole("list", { name: "Sources" })).toBeNull();
});

test("the page says what the agent is doing while it watches", () => {
  live.dimensions = { width: 1680, height: 1050 };
  const status = () => screen.getByRole("status", { name: "Agent" }).textContent;
  renderRoom();
  expect(status()).toBe("Mina is watching your screen");

  cleanup();
  live.assistant = "thinking";
  renderRoom();
  expect(status()).toBe("Mina is thinking");

  cleanup();
  live.assistant = "speaking";
  renderRoom();
  expect(status()).toBe("Mina is speaking");
});

test("the glow runs only while connected, sharing, and the agent is in the room", () => {
  const glow = () => screen.getByTestId("room").querySelector("[data-glow]");
  const cases = [
    { state: "connected", shared: true, agent: true, glow: "animated" },
    { state: "connecting", shared: true, agent: true, glow: "off" },
    { state: "disconnected", shared: true, agent: true, glow: "off" },
    { state: "connected", shared: false, agent: true, glow: "off" },
    { state: "connected", shared: true, agent: false, glow: "off" },
  ];
  for (const found of cases) {
    live.state = found.state;
    live.dimensions = found.shared ? { width: 1680, height: 1050 } : undefined;
    live.agentPresent = found.agent;
    renderRoom();

    expect(glow()?.getAttribute("data-glow"), JSON.stringify(found)).toBe(found.glow);
    expect(
      screen.getByRole("status", { name: "Agent" }).textContent === "",
      JSON.stringify(found),
    ).toBe(found.glow === "off");
    cleanup();
  }
});

test("with reduced motion the glow is a still ring, not an animation", () => {
  stubMatchMedia(true);
  live.dimensions = { width: 1680, height: 1050 };

  renderRoom();

  const room = screen.getByTestId("room");
  expect(room.querySelector("[data-glow]")?.getAttribute("data-glow")).toBe("static");
  expect(room.querySelector("[data-beam]")).toBeNull();
});

test("the pointer lands inside the picture, not in the bars around it", () => {
  live.dimensions = { width: 1680, height: 1050 };
  renderRoom();

  send("hud", { kind: "point", x: 0.5, y: 0.5, label: "Review status" });

  expect(screen.getByTestId("agent-cursor").style.transform).toBe(
    "translate3d(400px, 225px, 0)",
  );
  expect(screen.getByRole("status", { name: "Pointer" }).textContent).toBe(
    "Mina points at Review status",
  );
  expect(within(screen.getByTestId("agent-cursor-tag")).getByText("Mina")).toBeDefined();
});

test("a proposed ticket shows an approval card once and creates nothing by itself", () => {
  const calls = stubApi(() => ({ status: 200, body: null }));
  renderRoom();
  const proposal = {
    id: "e1",
    title: "Cannot reset",
    body: "Cannot reset\n\nReason for handoff: SSO",
  };

  send("escalation", proposal);
  send("escalation", proposal);
  send("escalation", { nonsense: true });

  const cards = screen.getAllByRole("region", { name: "Proposed ticket" });
  expect(cards).toHaveLength(1);
  expect(within(cards[0]!).getByRole("heading", { name: "Cannot reset" })).toBeDefined();
  expect(within(cards[0]!).getByRole("button", { name: "Approve ticket" })).toBeDefined();
  expect(calls).toEqual([]);
});
