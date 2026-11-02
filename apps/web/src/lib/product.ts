import { errorDetail, type Product, type ProductWrite } from "@/lib/api/client";

export type ProductLoad =
  | { status: "ready"; product: Product }
  | { status: "missing" }
  | { status: "error"; message: string };

export const emptyDraft: ProductWrite = {
  name: "",
  description: "",
  tone: "",
  refusal_rules: "",
};

export function productLoad(
  status: number,
  product: Product | undefined,
  error: unknown,
): ProductLoad {
  if (status === 404) {
    return { status: "missing" };
  }
  if (product === undefined) {
    return { status: "error", message: errorDetail(error, "Could not load the product.") };
  }
  return { status: "ready", product };
}

export function indexedLabel(count: number): string {
  return count === 1 ? "Indexed 1 chunk." : `Indexed ${count} chunks.`;
}
