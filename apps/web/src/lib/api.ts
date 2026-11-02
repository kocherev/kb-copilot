import { productFromResponse, type ProductLoad } from "@/lib/product";

export function publicApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

// Inside Compose the browser's API URL points at the web container itself.
export function serverApiUrl(): string {
  return process.env.API_INTERNAL_URL ?? publicApiUrl();
}

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

export async function loadProduct(id: string): Promise<ProductLoad> {
  try {
    const response = await fetch(apiPath(serverApiUrl(), `/products/${id}`));
    return productFromResponse(response.status, await readJson(response));
  } catch {
    return { status: "error", message: "Could not load the product." };
  }
}
