import { errorDetail } from "@/lib/api";

export type ProductDraft = {
  name: string;
  description: string;
  tone: string;
  refusal_rules: string;
};

export type Product = ProductDraft & {
  id: string;
};

export type ProductLoad =
  | { status: "ready"; product: Product }
  | { status: "missing" }
  | { status: "error"; message: string };

export const emptyDraft: ProductDraft = {
  name: "",
  description: "",
  tone: "",
  refusal_rules: "",
};

export function isProduct(body: unknown): body is Product {
  if (typeof body !== "object" || body === null) {
    return false;
  }
  const record = body as Record<string, unknown>;
  return (
    typeof record.id === "string" &&
    typeof record.name === "string" &&
    typeof record.description === "string" &&
    typeof record.tone === "string" &&
    typeof record.refusal_rules === "string"
  );
}

export function productFromResponse(status: number, body: unknown): ProductLoad {
  if (status === 404) {
    return { status: "missing" };
  }
  if (status < 200 || status >= 300 || !isProduct(body)) {
    return {
      status: "error",
      message: errorDetail(body, "Could not load the product."),
    };
  }
  return { status: "ready", product: body };
}

export function indexedLabel(count: number): string {
  return count === 1 ? "Indexed 1 chunk." : `Indexed ${count} chunks.`;
}
