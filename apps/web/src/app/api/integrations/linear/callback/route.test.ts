import { NextRequest } from "next/server";
import { beforeEach, expect, test, vi } from "vitest";

import { GET } from "@/app/api/integrations/linear/callback/route";

const api = vi.hoisted(() => ({ POST: vi.fn() }));
vi.mock("@/lib/api/server", () => ({ serverApi: async () => api }));

const callback = "http://localhost:3000/api/integrations/linear/callback";

beforeEach(() => api.POST.mockReset());

async function visit(query: string) {
  const response = await GET(new NextRequest(`${callback}?${query}`));
  return response.headers.get("location");
}

test("the code and state go to the API and the user lands on settings", async () => {
  api.POST.mockResolvedValue({ response: { ok: true } });

  expect(await visit("code=the-code&state=the-state")).toBe(
    "http://localhost:3000/settings?linear=connected",
  );
  expect(api.POST).toHaveBeenCalledWith("/integrations/linear/callback", {
    body: { code: "the-code", state: "the-state" },
  });
});

test("a refusal by the API or a failed call is a failure notice", async () => {
  api.POST.mockResolvedValueOnce({ response: { ok: false } });
  expect(await visit("code=c&state=s")).toBe("http://localhost:3000/settings?linear=failed");

  api.POST.mockRejectedValueOnce(new Error("down"));
  expect(await visit("code=c&state=s")).toBe("http://localhost:3000/settings?linear=failed");
});

test("a denied grant or a bare visit never reaches the API", async () => {
  expect(await visit("error=access_denied&state=s")).toBe(
    "http://localhost:3000/settings?linear=denied",
  );
  expect(await visit("state=s")).toBe("http://localhost:3000/settings?linear=failed");
  expect(api.POST).not.toHaveBeenCalled();
});
