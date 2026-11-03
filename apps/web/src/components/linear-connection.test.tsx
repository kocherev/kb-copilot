import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { LinearConnection } from "@/components/linear-connection";
import { stubApi } from "@/test/api-stub";

const connected = {
  enabled: true,
  connected: true,
  workspace_name: "Acme Inc",
  team_name: "Engineering",
  team_key: "ENG",
};
const open = { enabled: true, connected: false };

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderConnection(notice: "connected" | "denied" | "failed" | null = null) {
  render(<LinearConnection apiUrl="http://localhost:8000" notice={notice} />);
}

test("a connected workspace shows its team and can be disconnected", async () => {
  let status: object = connected;
  const calls = stubApi((call) => {
    if (call.method === "DELETE") {
      status = open;
      return { status: 204 };
    }
    return { status: 200, body: status };
  });
  renderConnection("connected");

  expect((await screen.findByText(/Connected to Acme Inc/)).textContent).toContain(
    "Tickets go to Engineering (ENG)",
  );
  expect(screen.getByRole("status").textContent).toBe("Linear connected.");

  fireEvent.click(screen.getByRole("button", { name: "Disconnect Linear" }));

  expect(await screen.findByRole("button", { name: "Connect Linear" })).toBeDefined();
  expect(calls.find((call) => call.method === "DELETE")?.url).toBe(
    "http://localhost:8000/integrations/linear",
  );
});

test("connect opens the Linear authorize URL the API returns", async () => {
  const assign = vi.fn();
  stubApi((call) =>
    call.url.endsWith("/connect")
      ? { status: 200, body: { url: "https://linear.app/oauth/authorize?state=s" } }
      : { status: 200, body: open },
  );
  vi.stubGlobal("location", { assign });
  renderConnection();

  fireEvent.click(await screen.findByRole("button", { name: "Connect Linear" }));

  await vi.waitFor(() =>
    expect(assign).toHaveBeenCalledWith("https://linear.app/oauth/authorize?state=s"),
  );
});

test("a server without Linear settings says what to set and offers no button", async () => {
  stubApi(() => ({ status: 200, body: { enabled: false, connected: false } }));
  renderConnection("denied");

  expect(await screen.findByText(/LINEAR_TOKEN_KEY/)).toBeDefined();
  expect(screen.queryByRole("button", { name: "Connect Linear" })).toBeNull();
  expect(screen.getByRole("status").textContent).toBe("Linear access was not granted.");
});

test("a refused connect shows the API's reason", async () => {
  stubApi((call) =>
    call.url.endsWith("/connect")
      ? { status: 503, body: { detail: "Linear is not configured" } }
      : { status: 200, body: open },
  );
  renderConnection();

  fireEvent.click(await screen.findByRole("button", { name: "Connect Linear" }));

  expect((await screen.findByRole("alert")).textContent).toBe("Linear is not configured");
});
