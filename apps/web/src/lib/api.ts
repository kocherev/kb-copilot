export function apiPath(apiUrl: string, path: string): string {
  return `${apiUrl.replace(/\/+$/, "")}${path}`;
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
  return fallback;
}
