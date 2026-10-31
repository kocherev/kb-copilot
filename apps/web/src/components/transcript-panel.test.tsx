import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { TranscriptPanel } from "@/components/transcript-panel";

afterEach(() => {
  cleanup();
});

test("transcript shows an empty state, one character, and a long string", () => {
  const { rerender } = render(<TranscriptPanel lines={[]} />);

  expect(screen.getByText("Waiting for speech.")).toBeDefined();

  rerender(
    <TranscriptPanel
      lines={[{ id: "one", speaker: "You", text: "A", sources: [] }]}
    />,
  );
  expect(screen.getByText("A")).toBeDefined();
  expect(screen.queryByText("Waiting for speech.")).toBeNull();
  expect(screen.queryByRole("list", { name: "Sources" })).toBeNull();

  const long = "B".repeat(400);
  rerender(
    <TranscriptPanel
      lines={[{ id: "long", speaker: "Agent", text: long, sources: [] }]}
    />,
  );
  const text = screen.getByText(long);
  expect(text.className).toMatch(/anywhere/);
});

test("transcript shows a cited source and a not-in-docs answer", () => {
  const source = `file:///docs/${"c".repeat(180)}.md`;
  const { rerender } = render(
    <TranscriptPanel
      lines={[
        {
          id: "cited",
          speaker: "Agent",
          text: "Refunds take 5 business days.",
          sources: [source],
        },
      ]}
    />,
  );

  expect(screen.getByText("Refunds take 5 business days.")).toBeDefined();
  const citation = screen.getByText(`Source: ${"c".repeat(180)}.md`);
  expect(citation.className).toMatch(/anywhere/);
  expect(citation.getAttribute("title")).toBe(source);
  expect(screen.getByRole("list", { name: "Sources" })).toBeDefined();

  rerender(
    <TranscriptPanel
      lines={[
        {
          id: "missing",
          speaker: "Agent",
          text: "That is not in the docs.",
          sources: [],
        },
      ]}
    />,
  );
  expect(screen.getByText("That is not in the docs.")).toBeDefined();
  expect(screen.queryByRole("list", { name: "Sources" })).toBeNull();
});
