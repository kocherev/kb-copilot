import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { SessionStart } from "@/components/session-start";

const transcriptions = vi.hoisted(() => ({
  current: [] as {
    text: string;
    participantInfo: { identity: string };
    streamInfo: { id: string };
  }[],
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
  useConnectionState: () => "connected",
  useTranscriptions: () => transcriptions.current,
  TrackToggle: ({
    "aria-label": label,
  }: {
    "aria-label"?: string;
  }) => <button type="button">{label}</button>,
}));

vi.mock("livekit-client", () => ({
  ConnectionState: { Connected: "connected" },
  Track: {
    Source: { Microphone: "microphone", ScreenShare: "screen_share" },
  },
}));

const productId = "11111111-1111-4111-8111-111111111111";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  transcriptions.current = [];
});

test("start session posts the product and joins with mic and screen", async () => {
  transcriptions.current = [
    {
      text: "C".repeat(80),
      participantInfo: { identity: "agent-1" },
      streamInfo: { id: "line-1" },
    },
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("http://localhost:8000/sessions");
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toEqual({ product_id: productId });
      return {
        ok: true,
        status: 201,
        json: async () => ({
          url: "ws://localhost:7880",
          token: "signed-token",
          room: "kb-room",
        }),
      };
    }),
  );

  render(
    <SessionStart
      apiUrl="http://localhost:8000"
      productId={productId}
      productName={"A".repeat(80)}
    />,
  );

  const heading = screen.getByRole("heading", { level: 1 });
  expect(heading.textContent).toBe("A".repeat(80));
  expect(heading.className).toMatch(/anywhere/);
  expect(screen.getByRole("link", { name: "Product" }).getAttribute("href")).toBe(
    `/products/${productId}`,
  );

  fireEvent.click(screen.getByRole("button", { name: "Start session" }));

  const room = await screen.findByText("In the room");
  const root = room.parentElement;
  expect(root?.getAttribute("data-url")).toBe("ws://localhost:7880");
  expect(root?.getAttribute("data-token")).toBe("signed-token");
  expect(root?.getAttribute("data-audio")).toBe("true");
  expect(root?.getAttribute("data-video")).toBe("false");
  expect(root?.getAttribute("data-screen")).toBe("true");
  expect(root?.getAttribute("data-connect")).toBe("true");
  expect(screen.getByTestId("agent-audio")).toBeDefined();
  expect(screen.getByRole("button", { name: "Microphone" })).toBeDefined();
  expect(screen.getByRole("button", { name: "Screen share" })).toBeDefined();
  const spoken = screen.getByText("C".repeat(80));
  expect(spoken.className).toMatch(/anywhere/);
  expect(screen.getByText("Agent")).toBeDefined();
  expect(screen.queryByRole("list", { name: "Sources" })).toBeNull();
});

test("session transcript shows a cited source from the agent", async () => {
  transcriptions.current = [
    {
      text: "Refunds take 5 business days.\nSource: file:///docs/billing.md",
      participantInfo: { identity: "agent-1" },
      streamInfo: { id: "cited" },
    },
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      status: 201,
      json: async () => ({
        url: "ws://localhost:7880",
        token: "signed-token",
        room: "kb-room",
      }),
    })),
  );

  render(
    <SessionStart
      apiUrl="http://localhost:8000"
      productId={productId}
      productName="Acme"
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Start session" }));

  expect(await screen.findByText("Refunds take 5 business days.")).toBeDefined();
  expect(screen.getByText("Source: billing.md")).toBeDefined();
  expect(screen.getByRole("list", { name: "Sources" })).toBeDefined();
});

test("a refused session shows the error", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      status: 404,
      json: async () => ({ detail: "product not found" }),
    })),
  );
  render(
    <SessionStart apiUrl="http://localhost:8000" productId={productId} productName="A" />,
  );

  expect(screen.getByRole("heading", { level: 1, name: "A" })).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Start session" }));

  expect(await screen.findByRole("alert")).toBeDefined();
  expect(screen.getByRole("alert").textContent).toBe("Product not found.");
});
