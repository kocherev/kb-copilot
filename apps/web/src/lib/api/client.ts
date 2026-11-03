import createClient, { type Client } from "openapi-fetch";

import type { components, paths } from "@/lib/api/schema";

export type ApiClient = Client<paths>;
export type Product = components["schemas"]["Product"];
export type ProductSummary = components["schemas"]["ProductSummary"];
export type ProductWrite = components["schemas"]["ProductWrite"];
export type SessionGrant = components["schemas"]["SessionGrant"];
export type SessionSummary = components["schemas"]["SessionSummary"];
export type Replay = components["schemas"]["Replay"];
export type Turn = components["schemas"]["Turn"];
export type IngestJob = components["schemas"]["IngestJob"];
export type Escalation = components["schemas"]["Escalation"];
export type LinearStatus = components["schemas"]["LinearStatus"];

export function publicApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export function apiPath(apiUrl: string, path: string): string {
  return `${apiUrl.replace(/\/+$/, "")}${path}`;
}

// Calls fetch at request time so tests can stub the global.
export function apiClient(apiUrl: string, token: () => Promise<string>): ApiClient {
  const client = createClient<paths>({
    baseUrl: apiUrl.replace(/\/+$/, ""),
    fetch: (request) => fetch(request),
  });
  client.use({
    async onRequest({ request }) {
      request.headers.set("authorization", `Bearer ${await token()}`);
      return request;
    },
  });
  return client;
}

// The Better Auth JWT for the signed-in browser session.
export async function browserToken(): Promise<string> {
  const response = await fetch("/api/auth/token");
  const body: unknown = await response.json().catch(() => null);
  if (
    !response.ok ||
    typeof body !== "object" ||
    body === null ||
    !("token" in body) ||
    typeof body.token !== "string"
  ) {
    throw new Error("Sign in again.");
  }
  return body.token;
}

export function browserApi(apiUrl: string): ApiClient {
  return apiClient(apiUrl, browserToken);
}

export async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export function errorDetail(body: unknown, fallback: string): string {
  if (typeof body !== "object" || body === null || !("detail" in body)) {
    return fallback;
  }
  const detail = body.detail;
  if (typeof detail === "string" && detail) {
    return detail;
  }
  // A 422 lists field errors. Show the first one with its field name.
  if (Array.isArray(detail)) {
    const first: unknown = detail[0];
    if (typeof first === "object" && first !== null && "msg" in first && "loc" in first) {
      const field = Array.isArray(first.loc) ? first.loc.at(-1) : undefined;
      return typeof field === "string"
        ? `${field.replaceAll("_", " ")}: ${String(first.msg)}`
        : String(first.msg);
    }
  }
  return fallback;
}
