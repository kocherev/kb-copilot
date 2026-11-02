import { vi } from "vitest";

export const TEST_JWT = "test-jwt";

export type ApiCall = {
  method: string;
  url: string;
  authorization: string | null;
  json: unknown;
  form: FormData | null;
};

export type ApiReply = { status: number; body?: unknown; text?: string };

// Stubs fetch: the Better Auth token endpoint answers with TEST_JWT and every
// API call is recorded and answered by `reply`.
export function stubApi(reply: (call: ApiCall) => ApiReply): ApiCall[] {
  const calls: ApiCall[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === "/api/auth/token") {
        return Response.json({ token: TEST_JWT });
      }
      const call =
        input instanceof Request
          ? {
              method: input.method,
              url: input.url,
              authorization: input.headers.get("authorization"),
              json: input.body ? await input.json() : null,
              form: null,
            }
          : {
              method: init?.method ?? "GET",
              url: String(input),
              authorization: new Headers(init?.headers).get("authorization"),
              json: null,
              form: init?.body instanceof FormData ? init.body : null,
            };
      calls.push(call);
      const { status, body, text } = reply(call);
      // A 204 cannot carry a body.
      return new Response(status === 204 ? null : (text ?? JSON.stringify(body ?? null)), {
        status,
        headers: { "content-type": "application/json" },
      });
    }),
  );
  return calls;
}
