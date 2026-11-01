import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { ScreenHud } from "@/components/screen-hud";

afterEach(() => {
  cleanup();
});

test("the preview shows a thinking pulse and a named highlight", () => {
  const { rerender } = render(<ScreenHud thinking={false} point={null} />);
  const quiet = screen.getByText("Thinking");
  expect(quiet.className).toMatch(/opacity-0/);
  expect(screen.queryByText("Review status")).toBeNull();

  rerender(
    <ScreenHud thinking point={{ x: 0.25, y: 0.5, label: "Review status" }} />,
  );

  expect(screen.getByText("Thinking").className).toMatch(/opacity-100/);
  const label = screen.getByText("Review status");
  expect(label.className).toMatch(/anywhere/);
  const mark = label.parentElement;
  expect(mark?.getAttribute("style")).toContain("left: 25%");
  expect(mark?.getAttribute("style")).toContain("top: 50%");
});
