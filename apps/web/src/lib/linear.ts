export type LinearNotice = "connected" | "denied" | "failed";

const notices: readonly string[] = ["connected", "denied", "failed"];

// The callback route puts the outcome in the query of the settings page.
export function linearNotice(value: string | string[] | undefined): LinearNotice | null {
  return typeof value === "string" && notices.includes(value)
    ? (value as LinearNotice)
    : null;
}
