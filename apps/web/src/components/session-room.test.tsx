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
  phase: undefined as string | undefined,
  handlers: {} as Record<string, (message: { payload: Uint8Array }) => void>,
  disconnect: vi.fn(),
  dimensions: undefined as { width: number; height: number } | undefined,
  participants: [] as { identity: string }[],
  sent: [] as { topic: string; body: unknown; reliable: boolean }[],
  enabled: { microphone: true, screen_share: true } as Record<string, boolean>,
  toggled: [] as { source: string; force: boolean | undefined }[],
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
    handler?: (message: { payload: Uint8Array }) => void,
  ) => {
    if (handler) {
      live.handlers[topic] = handler;
    }
    return {
      send: async (payload: Uint8Array, options: { reliable?: boolean }) => {
        live.sent.push({
          topic,
          body: JSON.parse(new TextDecoder().decode(payload)),
          reliable: options.reliable === true,
        });
      },
    };
  },
  useRemoteParticipants: () => live.participants,
  useRoomContext: () => ({ disconnect: live.disconnect }),
  useTracks: () =>
    live.dimensions ? [{ publication: { dimensions: live.dimensions } }] : [],
  useTranscriptions: () => live.transcriptions,
  useVoiceAssistant: () => ({
    state: live.assistant,
    agent: live.agentPresent ? {} : undefined,
    agentAttributes: live.phase ? { "kb.phase": live.phase } : {},
  }),
  useTrackToggle: ({ source }: { source: string }) => ({
    enabled: live.enabled[source] ?? false,
    pending: false,
    toggle: async (force?: boolean) => {
      live.toggled.push({ source, force });
    },
  }),
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
  live.phase = undefined;
  live.handlers = {};
  live.dimensions = undefined;
  live.participants = [];
  live.sent = [];
  live.enabled = { microphone: true, screen_share: true };
  live.toggled = [];
  live.disconnect.mockReset();
  document.querySelectorAll("iframe").forEach((frame) => frame.remove());
  delete document.documentElement.dataset.theme;
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
      room="kb-room-1"
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
  expect(screen.getByRole("status", { name: "Agent" }).textContent).toBe(
    "Share your screen so Mina can see it",
  );
});

test("while connecting, only the phase line says so, not a second badge", () => {
  live.state = "connecting";

  renderRoom();

  expect(screen.queryByRole("status", { name: "Connection" })).toBeNull();
});

test.each([
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
  expect(screen.queryByRole("region", { name: "Your Mac" })).toBeNull();
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

test("the glow runs only while connected, sharing, and the agent is in the room, and the page says why", () => {
  const glow = () => screen.getByTestId("room").querySelector("[data-glow]");
  const cases = [
    { state: "connected", shared: true, agent: true, glow: "animated", says: "Mina is watching your screen" },
    { state: "connecting", shared: true, agent: true, glow: "off", says: "Connecting" },
    { state: "reconnecting", shared: true, agent: true, glow: "off", says: "" },
    { state: "disconnected", shared: true, agent: true, glow: "off", says: "" },
    { state: "connected", shared: false, agent: true, glow: "off", says: "Share your screen so Mina can see it" },
    { state: "connected", shared: true, agent: false, glow: "off", says: "Mina is joining" },
  ];
  for (const found of cases) {
    live.state = found.state;
    live.dimensions = found.shared ? { width: 1680, height: 1050 } : undefined;
    live.agentPresent = found.agent;
    renderRoom();

    expect(glow()?.getAttribute("data-glow"), JSON.stringify(found)).toBe(found.glow);
    expect(
      screen.getByRole("status", { name: "Agent" }).textContent,
      JSON.stringify(found),
    ).toBe(found.says);
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

const step = {
  kind: "proposal",
  id: "p1",
  task: "t1",
  description: "Click Update card",
  x: 0.5,
  y: 0.5,
  needs_approval: true,
  warning: "",
};

test("a proposed step waits in the tray, points at its target, and is allowed once", () => {
  live.dimensions = { width: 1680, height: 1050 };
  renderRoom();

  send("computer", step);

  const tray = screen.getByRole("region", { name: "Action approval" });
  expect(within(tray).getByRole("heading", { name: "Click Update card" })).toBeDefined();
  expect(within(tray).getByRole("status").textContent).toBe(
    "Mina wants to do this on your Mac. Nothing happens until you choose.",
  );
  expect(document.activeElement).toBe(tray);
  expect(screen.getByTestId("agent-cursor").getAttribute("data-state")).toBe("about-to-click");
  expect(screen.getByRole("status", { name: "Pointer" }).textContent).toBe(
    "Mina is about to click Click Update card",
  );
  expect(live.sent).toEqual([]);

  fireEvent.click(within(tray).getByRole("button", { name: "Allow once" }));

  expect(live.sent).toEqual([
    { topic: "computer-decision", body: { id: "p1", decision: "once" }, reliable: true },
  ]);
  expect(screen.queryByRole("region", { name: "Action approval" })).toBeNull();

  send("hud", { kind: "clicking", x: 0.5, y: 0.5, label: "Click Update card" });
  expect(screen.getByTestId("agent-cursor").getAttribute("data-state")).toBe("clicking");
});

test.each([
  ["Allow for this task", "task"],
  ["Stop", "stop"],
])("%s sends %s", (button, decision) => {
  renderRoom();
  send("computer", step);

  fireEvent.click(screen.getByRole("button", { name: button }));

  expect(live.sent.map((sent) => sent.body)).toEqual([{ id: "p1", decision }]);
});

test("Escape in the tray stops the task and hides the pointer", () => {
  live.dimensions = { width: 1680, height: 1050 };
  renderRoom();
  send("computer", step);

  fireEvent.keyDown(screen.getByRole("region", { name: "Action approval" }), {
    key: "Escape",
  });

  expect(live.sent.map((sent) => sent.body)).toEqual([{ id: "p1", decision: "stop" }]);
  expect(screen.getByTestId("agent-cursor").className).toContain("invisible");
});

test("a step the user allowed for the task offers only Stop, with a safety warning", () => {
  renderRoom();

  send("computer", { ...step, needs_approval: false, warning: "This deletes data." });

  const tray = screen.getByRole("region", { name: "Action approval" });
  expect(within(tray).getByRole("status").textContent).toBe("Mina is doing this on your Mac.");
  expect(within(tray).queryByRole("button", { name: "Allow once" })).toBeNull();
  expect(within(tray).getByRole("button", { name: "Stop" })).toBeDefined();
  expect(within(tray).getByRole("alert").textContent).toBe(
    "Check before you allow it: This deletes data.",
  );
});

test("the tray and the waiting pointer go when the task ends", () => {
  live.dimensions = { width: 1680, height: 1050 };
  renderRoom();
  send("computer", step);

  send("computer", { kind: "ended", task: "t1", reason: "timed_out" });
  send("computer", { kind: "proposal", id: "", task: "t1" });

  expect(screen.queryByRole("region", { name: "Action approval" })).toBeNull();
  expect(screen.getByTestId("agent-cursor").className).toContain("invisible");
});

test("without the helper the page offers the command that connects the Mac", async () => {
  const calls = stubApi(() => ({
    status: 200,
    body: { url: "wss://lk.example", token: "desktop-jwt" },
  }));
  const writeText = vi.fn(async () => {});
  vi.stubGlobal("navigator", { clipboard: { writeText } });
  renderRoom();
  const panel = screen.getByRole("region", { name: "Your Mac" });
  expect(within(panel).getByRole("status").textContent).toBe(
    "Your Mac is not connected. Mina can point, not click.",
  );

  fireEvent.click(within(panel).getByRole("button", { name: "Connect your Mac" }));

  const command =
    "uv run --package kb-desktop kb-desktop --url wss://lk.example --token desktop-jwt";
  expect(await within(panel).findByText(command)).toBeDefined();
  expect(calls.map((call) => [call.method, call.url, call.authorization])).toEqual([
    ["POST", "http://localhost:8000/sessions/kb-room-1/desktop-token", "Bearer test-jwt"],
  ]);
  fireEvent.click(within(panel).getByRole("button", { name: "Copy command" }));
  expect(await within(panel).findByRole("button", { name: "Copied" })).toBeDefined();
  expect(writeText).toHaveBeenCalledWith(command);
});

test("a token the API refuses is explained", async () => {
  stubApi(() => ({ status: 404, body: { detail: "session not found" } }));
  renderRoom();

  fireEvent.click(screen.getByRole("button", { name: "Connect your Mac" }));

  expect((await screen.findByRole("alert")).textContent).toBe("session not found");
});

test("with the helper in the room the page says the Mac is connected", () => {
  live.participants = [{ identity: "agent-1" }, { identity: "desktop:user-a" }];

  renderRoom();

  const panel = screen.getByRole("region", { name: "Your Mac" });
  expect(within(panel).getByRole("status").textContent).toBe(
    "Your Mac is connected. Mina asks before every click or keystroke.",
  );
  expect(within(panel).queryByRole("button")).toBeNull();
});

test("the control bar toggles show and switch the microphone and the screen", () => {
  live.enabled = { microphone: false, screen_share: true };
  renderRoom();

  const controls = screen.getByRole("group", { name: "Session controls" });
  const mic = within(controls).getByRole("button", { name: "Microphone" });
  const share = within(controls).getByRole("button", { name: "Screen share" });
  expect(mic.getAttribute("aria-pressed")).toBe("false");
  expect(share.getAttribute("aria-pressed")).toBe("true");

  fireEvent.click(mic);
  fireEvent.click(share);

  expect(live.toggled).toEqual([
    { source: "microphone", force: undefined },
    { source: "screen_share", force: undefined },
  ]);
});

test("a connected room without a shared screen offers to share it", () => {
  renderRoom();

  fireEvent.click(screen.getByRole("button", { name: "Share your screen" }));

  expect(live.toggled).toEqual([{ source: "screen_share", force: true }]);
});

test("while the room connects the stage says so and the controls stay", () => {
  live.state = "connecting";
  renderRoom();

  expect(screen.getByText("Connecting…")).toBeDefined();
  expect(screen.getByRole("button", { name: "End session" })).toBeDefined();
});

test("while the agent waits for the screen the stage asks for it, even if a share is starting", () => {
  live.phase = "waiting_for_screen";
  live.dimensions = { width: 1680, height: 1050 };
  renderRoom();

  expect(screen.getByRole("status", { name: "Agent" }).textContent).toBe(
    "Share your screen so Mina can see it",
  );
  const stage = screen.getByRole("region", { name: "Shared screen" });
  expect(within(stage).getByText("Mina starts talking once your screen is shared.")).toBeDefined();
  expect(within(stage).queryByTestId("shared-video")).toBeNull();
  expect(stage.querySelector("[data-glow]")?.getAttribute("data-glow")).toBe("off");

  fireEvent.click(within(stage).getByRole("button", { name: "Share your screen" }));

  expect(live.toggled).toEqual([{ source: "screen_share", force: true }]);
});

test("once the agent is live the stage shows the shared screen", () => {
  live.phase = "live";
  live.dimensions = { width: 1680, height: 1050 };
  renderRoom();

  const stage = screen.getByRole("region", { name: "Shared screen" });
  expect(within(stage).getByTestId("shared-video")).toBeDefined();
  expect(within(stage).queryByRole("button", { name: "Share your screen" })).toBeNull();
  expect(screen.getByRole("status", { name: "Agent" }).textContent).toBe(
    "Mina is watching your screen",
  );
});

test("a share that stops mid-call asks for the screen again", () => {
  live.phase = "live";
  renderRoom();

  expect(screen.getByRole("status", { name: "Agent" }).textContent).toBe(
    "Screen sharing stopped, so Mina can’t see your screen",
  );
  const stage = screen.getByRole("region", { name: "Shared screen" });
  expect(
    within(stage).getByText("Mina can’t see your screen until you share it again."),
  ).toBeDefined();
  fireEvent.click(within(stage).getByRole("button", { name: "Share your screen" }));
  expect(live.toggled).toEqual([{ source: "screen_share", force: true }]);
});

test("an agent that gives up and leaves is not shown as joining", () => {
  const onRestart = vi.fn();
  renderRoom(onRestart);
  send("agent-error", { message: "No screen was shared, so the session ended." });

  cleanup();
  live.agentPresent = false;
  renderRoom(onRestart);
  send("agent-error", { message: "No screen was shared, so the session ended." });

  expect(screen.getByRole("status", { name: "Agent" }).textContent).toBe("Mina left the call");
  expect(screen.getByRole("alert").textContent).toBe(
    "No screen was shared, so the session ended.",
  );
  fireEvent.click(screen.getByRole("button", { name: "New session" }));
  expect(onRestart).toHaveBeenCalledOnce();
});

test("without Document Picture-in-Picture there is no keep-on-top button", () => {
  renderRoom();

  expect(screen.queryByRole("button", { name: "Keep Mina on top" })).toBeNull();
});

// A real jsdom window from an iframe stands in for the floating window.
function stubPictureInPicture() {
  const frame = document.createElement("iframe");
  document.body.append(frame);
  const floating = frame.contentWindow!;
  const close = vi.spyOn(floating, "close");
  const requested: { width: number; height: number }[] = [];
  vi.stubGlobal("documentPictureInPicture", {
    requestWindow: async (size: { width: number; height: number }) => {
      requested.push(size);
      return floating;
    },
  });
  return { floating, close, requested };
}

test("keep on top opens a small window with the agent's state, pointer, mute and end", async () => {
  const { floating, close, requested } = stubPictureInPicture();
  document.documentElement.dataset.theme = "dark";
  live.phase = "live";
  live.dimensions = { width: 1680, height: 1050 };
  renderRoom();

  const button = screen.getByRole("button", { name: "Keep Mina on top" });
  expect(button.getAttribute("aria-pressed")).toBe("false");
  await act(async () => fireEvent.click(button));

  expect(requested).toEqual([{ width: 320, height: 200 }]);
  expect(button.getAttribute("aria-pressed")).toBe("true");
  expect(floating.document.title).toBe("Mina");
  expect(floating.document.documentElement.dataset.theme).toBe("dark");
  const pip = within(floating.document.body);
  expect(pip.getByRole("heading", { name: "Mina" })).toBeDefined();
  expect(pip.getByRole("status", { name: "Agent" }).textContent).toBe(
    "Watching your screen",
  );
  expect(
    pip.getByText("When Mina points at something on your screen, it shows here."),
  ).toBeDefined();

  send("computer", step);
  expect(pip.getByRole("status", { name: "Pointer" }).textContent).toBe(
    "Waiting for your OKClick Update card",
  );
  send("hud", { kind: "point", x: 0.9, y: 0.1, label: "Billing" });
  expect(pip.getByRole("status", { name: "Pointer" }).textContent).toBe("Look atBilling");

  const controls = pip.getByRole("group", { name: "Session controls" });
  fireEvent.click(within(controls).getByRole("button", { name: "Microphone" }));
  expect(live.toggled).toEqual([{ source: "microphone", force: undefined }]);
  fireEvent.click(within(controls).getByRole("button", { name: "End session" }));
  expect(live.disconnect).toHaveBeenCalledOnce();

  document.documentElement.dataset.theme = "light";
  await act(async () => {});
  expect(floating.document.documentElement.dataset.theme).toBe("light");
  expect(close).not.toHaveBeenCalled();
  cleanup();
  expect(close).toHaveBeenCalled();
});

test("the window opens right after the user shares the screen, and closes when the session ends", async () => {
  const { floating, close } = stubPictureInPicture();
  live.phase = "waiting_for_screen";
  const view = render(
    <SessionRoom
      url="ws://localhost:7880"
      token="signed-token"
      room="kb-room-1"
      apiUrl="http://localhost:8000"
      agentName="Mina"
      onRestart={() => {}}
    />,
  );

  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Share your screen" })));

  expect(live.toggled).toEqual([{ source: "screen_share", force: true }]);
  expect(
    within(floating.document.body).getByRole("status", { name: "Agent" }).textContent,
  ).toBe("Share your screen so Mina can see it");

  live.state = "disconnected";
  view.rerender(
    <SessionRoom
      url="ws://localhost:7880"
      token="signed-token"
      room="kb-room-1"
      apiUrl="http://localhost:8000"
      agentName="Mina"
      onRestart={() => {}}
    />,
  );
  expect(close).toHaveBeenCalled();
});

test("a window the browser refuses leaves the button to try again", async () => {
  vi.stubGlobal("documentPictureInPicture", {
    requestWindow: async () => {
      throw new DOMException("No user activation", "NotAllowedError");
    },
  });
  live.phase = "waiting_for_screen";
  renderRoom();

  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Share your screen" })));

  expect(live.toggled).toEqual([{ source: "screen_share", force: true }]);
  expect(screen.getByRole("button", { name: "Keep Mina on top" }).getAttribute("aria-pressed")).toBe(
    "false",
  );
  expect(screen.queryByRole("alert")).toBeNull();
});
