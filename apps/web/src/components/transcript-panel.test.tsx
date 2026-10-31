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
    <TranscriptPanel lines={[{ id: "one", speaker: "You", text: "A" }]} />,
  );
  expect(screen.getByText("A")).toBeDefined();
  expect(screen.queryByText("Waiting for speech.")).toBeNull();

  const long = "B".repeat(400);
  rerender(
    <TranscriptPanel lines={[{ id: "long", speaker: "Agent", text: long }]} />,
  );
  const text = screen.getByText(long);
  expect(text.className).toMatch(/anywhere/);
});
