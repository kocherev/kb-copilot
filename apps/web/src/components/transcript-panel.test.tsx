import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { TranscriptPanel } from "@/components/transcript-panel";

afterEach(() => {
  cleanup();
});

const passage = {
  id: "p1",
  title: "Refund timing",
  source: `file:///docs/${"c".repeat(180)}.md`,
  anchor: "refund-timing",
  snippet: "Refunds reach the card in five business days.",
};

test("transcript shows an empty state, one character, and a long string", () => {
  const { rerender } = render(<TranscriptPanel lines={[]} />);

  expect(screen.getByText("Waiting for speech.")).toBeDefined();
  expect(screen.getByRole("log")).toBeDefined();

  rerender(
    <TranscriptPanel
      lines={[{ id: "one", speaker: "You", text: "A", citations: [] }]}
    />,
  );
  expect(screen.getByText("A")).toBeDefined();
  expect(screen.queryByText("Waiting for speech.")).toBeNull();
  expect(screen.queryByRole("list", { name: "Sources" })).toBeNull();

  const long = "B".repeat(400);
  rerender(
    <TranscriptPanel
      lines={[{ id: "long", speaker: "Agent", text: long, citations: [] }]}
    />,
  );
  expect(screen.getByText(long).className).toMatch(/anywhere/);
});

test("a cited answer shows the section title and an expandable snippet", () => {
  render(
    <TranscriptPanel
      lines={[
        {
          id: "cited",
          speaker: "Agent",
          text: "Refunds take 5 business days.",
          citations: [passage],
        },
      ]}
    />,
  );

  expect(screen.getByText("Refunds take 5 business days.")).toBeDefined();
  expect(screen.getByRole("list", { name: "Sources" })).toBeDefined();
  expect(screen.getByText(/Refund timing/)).toBeDefined();
  expect(screen.getByText(`(${"c".repeat(180)}.md)`)).toBeDefined();
  const snippet = screen.getByText("Refunds reach the card in five business days.");
  expect(snippet.closest("details")?.hasAttribute("open")).toBe(false);
});
