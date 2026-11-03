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
  agent_name: "Shawn",
  voice: "Sulafat",
};

// Gemini prebuilt voices, with the trait the speech generation docs give each.
// The first is the default. A test fails when this list drifts from the API.
export const voices: readonly { value: ProductWrite["voice"]; trait: string }[] = [
  { value: "Sulafat", trait: "Warm" },
  { value: "Achird", trait: "Friendly" },
  { value: "Puck", trait: "Upbeat" },
  { value: "Aoede", trait: "Breezy" },
  { value: "Sadachbia", trait: "Lively" },
  { value: "Vindemiatrix", trait: "Gentle" },
];

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
