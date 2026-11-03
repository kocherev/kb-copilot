import { expect, test } from "vitest";

import { letterbox } from "@/lib/letterbox";

const stage = { width: 800, height: 450 };

test("a 16:9 frame fills a 16:9 stage", () => {
  expect(letterbox(stage, { width: 1920, height: 1080 })).toEqual({
    left: 0,
    top: 0,
    width: 800,
    height: 450,
  });
});

test("a 16:10 frame leaves bars left and right", () => {
  const box = letterbox(stage, { width: 1680, height: 1050 });

  expect(box.height).toBe(450);
  expect(box.width).toBe(720);
  expect(box.left).toBe(40);
  expect(box.top).toBe(0);
});

test("a tall frame is centered with wide bars", () => {
  const box = letterbox(stage, { width: 900, height: 1600 });

  expect(box.height).toBe(450);
  expect(box.width).toBeCloseTo(253.125);
  expect(box.left).toBeCloseTo((800 - 253.125) / 2);
  expect(box.top).toBe(0);
});

test("a wide frame leaves bars above and below", () => {
  const box = letterbox(stage, { width: 2000, height: 500 });

  expect(box.width).toBe(800);
  expect(box.height).toBe(200);
  expect(box.top).toBe(125);
});

test("an unknown frame size uses the whole stage", () => {
  expect(letterbox(stage, { width: 0, height: 0 })).toEqual({
    left: 0,
    top: 0,
    width: 800,
    height: 450,
  });
});
