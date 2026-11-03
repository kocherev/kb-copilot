import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { AgentCursor, IDLE_MS } from "@/components/agent-cursor/agent-cursor";
import type { HudPoint } from "@/lib/protocol";

const container = { width: 800, height: 450 };
const video = { width: 1920, height: 1080 };
const review: HudPoint = { kind: "point", x: 0.25, y: 0.5, label: "Review status" };

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function show(point: HudPoint | null, thinking = false) {
  return (
    <AgentCursor
      name="Mina"
      point={point}
      thinking={thinking}
      container={container}
      video={video}
    />
  );
}

const announced = () => screen.getByRole("status", { name: "Pointer" }).textContent;
const isHidden = () => screen.getByTestId("agent-cursor").className.includes("invisible");

test("the cursor stays hidden until the agent points", () => {
  render(show(null));

  expect(isHidden()).toBe(true);
  expect(announced()).toBe("");
});

test("a point shows the cursor with the agent name and the label, then it fades out", () => {
  const view = render(show(null));

  view.rerender(show(review));

  expect(isHidden()).toBe(false);
  expect(announced()).toBe("Mina points at Review status");
  expect(screen.getByTestId("agent-cursor").style.transform).toBe(
    "translate3d(200px, 225px, 0)",
  );
  act(() => {
    vi.advanceTimersByTime(IDLE_MS - 1);
  });
  expect(isHidden()).toBe(false);
  act(() => {
    vi.advanceTimersByTime(1);
  });
  expect(isHidden()).toBe(true);
  expect(announced()).toBe("");
});

test("a new point moves the cursor and restarts the idle time", () => {
  const view = render(show(review));
  act(() => {
    vi.advanceTimersByTime(IDLE_MS - 100);
  });

  view.rerender(show({ kind: "point", x: 0.5, y: 0.5, label: "Save" }));
  act(() => {
    vi.advanceTimersByTime(IDLE_MS - 100);
  });

  expect(isHidden()).toBe(false);
  expect(screen.getByTestId("agent-cursor").style.transform).toBe(
    "translate3d(400px, 225px, 0)",
  );
  act(() => {
    vi.advanceTimersByTime(100);
  });
  expect(isHidden()).toBe(true);
});

test("after it hides, the next point brings it back from where it was", () => {
  const view = render(show(review));
  act(() => {
    vi.advanceTimersByTime(IDLE_MS);
  });
  expect(isHidden()).toBe(true);
  expect(screen.getByTestId("agent-cursor").style.transform).toBe(
    "translate3d(200px, 225px, 0)",
  );

  view.rerender(show({ kind: "point", x: 0.75, y: 0.25, label: "Next" }));

  expect(isHidden()).toBe(false);
  expect(screen.getByTestId("agent-cursor").style.transform).toBe(
    "translate3d(600px, 112.5px, 0)",
  );
});

test("thinking dots show in the tag while the agent thinks after pointing", () => {
  const view = render(show(review));
  const cursor = () => screen.getByTestId("agent-cursor");
  const dots = () =>
    screen.getByTestId("agent-cursor-tag").querySelectorAll("[aria-hidden] > span");
  expect(cursor().getAttribute("data-state")).toBe("pointing");
  expect(dots()).toHaveLength(0);

  view.rerender(show(review, true));

  expect(cursor().getAttribute("data-state")).toBe("thinking");
  expect(dots()).toHaveLength(3);
});

test("the tag flips to the left of the arrow near the right edge", () => {
  const view = render(show(review));
  expect(screen.getByTestId("agent-cursor-tag").style.left).not.toBe("");

  view.rerender(show({ kind: "point", x: 0.9, y: 0.5, label: "Menu" }));

  const tag = screen.getByTestId("agent-cursor-tag");
  expect(tag.style.right).not.toBe("");
  expect(tag.style.left).toBe("");
});

test("a click waiting for approval rings and stays until the agent moves on", () => {
  const view = render(show(null));

  view.rerender(show({ kind: "about-to-click", x: 0.5, y: 0.5, label: "Save" }));
  act(() => {
    vi.advanceTimersByTime(IDLE_MS * 5);
  });

  expect(isHidden()).toBe(false);
  expect(screen.getByTestId("agent-cursor").getAttribute("data-state")).toBe("about-to-click");
  expect(screen.getByTestId("agent-cursor-ring")).toBeTruthy();
  expect(announced()).toBe("Mina is about to click Save");

  view.rerender(show(null));
  expect(isHidden()).toBe(true);
});

test("a click ripples, says so, and fades out like a point", () => {
  const view = render(show({ kind: "about-to-click", x: 0.5, y: 0.5, label: "Save" }));

  view.rerender(show({ kind: "clicking", x: 0.5, y: 0.5, label: "Save" }));

  expect(screen.getByTestId("agent-cursor").getAttribute("data-state")).toBe("clicking");
  expect(screen.getByTestId("agent-cursor-ring")).toBeTruthy();
  expect(announced()).toBe("Mina clicks Save");
  act(() => {
    vi.advanceTimersByTime(IDLE_MS);
  });
  expect(isHidden()).toBe(true);
});

test("a plain point has no ring", () => {
  render(show(review));

  expect(screen.queryByTestId("agent-cursor-ring")).toBeNull();
});

test("on a narrow stage the tag narrows to the space left in the picture", () => {
  const point: HudPoint = { kind: "point", x: 0.6, y: 0.5, label: "Update card" };
  const narrow = { width: 300, height: 169 };
  const view = render(
    <AgentCursor name="Mina" point={point} thinking={false} container={narrow} video={narrow} />,
  );
  const width = () => parseFloat(screen.getByTestId("agent-cursor-tag").style.maxWidth);

  expect(width()).toBeCloseTo(300 * 0.4 - (22 * 0.62) - 4);

  view.rerender(
    <AgentCursor name="Mina" point={point} thinking={false} container={container} video={video} />,
  );
  expect(width()).toBe(192);
});
