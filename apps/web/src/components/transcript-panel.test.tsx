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
  const { rerender } = render(<TranscriptPanel lines={[]} agentName="Mina" />);

  expect(screen.getByText("Nothing said yet")).toBeDefined();
  expect(screen.getByText(/Ask Mina a question out loud/)).toBeDefined();
  expect(screen.getByRole("log")).toBeDefined();

  rerender(
    <TranscriptPanel
      agentName="Mina"
      lines={[{ id: "one", speaker: "You", text: "A", citations: [] }]}
    />,
  );
  expect(screen.getByText("A")).toBeDefined();
  expect(screen.queryByText("Nothing said yet")).toBeNull();
  expect(screen.queryByRole("list", { name: "Sources" })).toBeNull();

  const long = "B".repeat(400);
  rerender(
    <TranscriptPanel
      agentName="Mina"
      lines={[{ id: "long", speaker: "Agent", text: long, citations: [] }]}
    />,
  );
  expect(screen.getByText(long).className).toMatch(/anywhere/);
});

test("a cited answer shows the section title and an expandable snippet", () => {
  render(
    <TranscriptPanel
      agentName="Mina"
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
  expect(screen.getByText("Mina")).toBeDefined();
  expect(screen.queryByText("Agent")).toBeNull();
  expect(screen.getByRole("list", { name: "Sources" })).toBeDefined();
  expect(screen.getByText(/Refund timing/)).toBeDefined();
  expect(screen.getByText(`${"c".repeat(180)}.md`)).toBeDefined();
  const snippet = screen.getByText("Refunds reach the card in five business days.");
  expect(snippet.closest("details")?.hasAttribute("open")).toBe(false);
});
