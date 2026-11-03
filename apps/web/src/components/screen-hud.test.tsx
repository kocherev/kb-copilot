import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { ScreenHud } from "@/components/screen-hud";

afterEach(() => {
  cleanup();
});

const container = { width: 800, height: 450 };
const video = { width: 1920, height: 1080 };

test("the thinking label exists only while thinking", () => {
  const { rerender } = render(
    <ScreenHud thinking={false} point={null} container={container} video={video} />,
  );
  expect(screen.queryByText("Thinking")).toBeNull();

  rerender(<ScreenHud thinking point={null} container={container} video={video} />);

  expect(screen.getByText("Thinking")).toBeDefined();
});

test("a named highlight sits at its fraction of the picture", () => {
  render(
    <ScreenHud
      thinking={false}
      point={{ x: 0.25, y: 0.5, label: "Review status" }}
      container={container}
      video={{ width: 900, height: 1600 }}
    />,
  );

  const label = screen.getByText("Review status");
  expect(label.className).toMatch(/anywhere/);
  const mark = label.parentElement;
  expect(mark?.getAttribute("style")).toContain("left: 25%");
  expect(mark?.getAttribute("style")).toContain("top: 50%");
  const frame = screen.getByTestId("hud-frame");
  expect(frame.style.height).toBe("450px");
  expect(Number.parseFloat(frame.style.left)).toBeCloseTo(273.4375);
});
