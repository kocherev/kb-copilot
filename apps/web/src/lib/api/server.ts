import { headers } from "next/headers";
import { connection } from "next/server";

import { apiClient, publicApiUrl, type ApiClient, type Product } from "@/lib/api/client";
import { auth } from "@/lib/auth";
import { productLoad, type ProductLoad } from "@/lib/product";
import { replayLoad, type ReplayLoad } from "@/lib/replay";

// Inside Compose the browser's API URL points at the web container itself.
export function serverApiUrl(): string {
  return process.env.API_INTERNAL_URL ?? publicApiUrl();
}

export async function serverApi(): Promise<ApiClient> {
  // openapi-fetch draws a Math.random request id, which Next refuses in a
  // prerender. headers() alone does not stop one: partial prefetching resolves
  // session data in the shell.
  await connection();
  const requestHeaders = await headers();
  return apiClient(serverApiUrl(), async () => {
    const { token } = await auth.api.getToken({ headers: requestHeaders });
    return token;
  });
}

export async function loadProduct(id: string): Promise<ProductLoad> {
  try {
    const api = await serverApi();
    const { data, error, response } = await api.GET("/products/{product_id}", {
      params: { path: { product_id: id } },
    });
    return productLoad(response.status, data, error);
  } catch {
    return { status: "error", message: "Could not load the product." };
  }
}

export async function loadReplay(id: string): Promise<ReplayLoad> {
  try {
    const api = await serverApi();
    const { data, error, response } = await api.GET("/sessions/{session_id}", {
      params: { path: { session_id: id } },
    });
    return replayLoad(response.status, data, error);
  } catch {
    return { status: "error", message: "Could not load the session." };
  }
}

export async function loadProducts(): Promise<Product[] | null> {
  try {
    const api = await serverApi();
    const { data } = await api.GET("/products");
    return data ?? null;
  } catch {
    return null;
  }
}
