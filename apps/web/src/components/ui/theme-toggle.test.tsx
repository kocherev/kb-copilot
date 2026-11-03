import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { ThemeToggle } from "@/components/ui/theme-toggle";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.dataset.theme = "light";
  vi.stubGlobal("matchMedia", () => ({
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("theme toggle offers system, light and dark, with system first", () => {
  render(<ThemeToggle />);

  const group = screen.getByRole("group", { name: "Theme" });
  expect(group).toBeDefined();
  expect(screen.getAllByRole("radio").map((radio) => radio.getAttribute("value"))).toEqual([
    "system",
    "light",
    "dark",
  ]);
  expect(screen.getByRole("radio", { name: "System" })).toHaveProperty("checked", true);
});

test("choosing dark switches the page and remembers it", () => {
  render(<ThemeToggle />);

  fireEvent.click(screen.getByRole("radio", { name: "Dark" }));

  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(screen.getByRole("radio", { name: "Dark" })).toHaveProperty("checked", true);
  cleanup();
  render(<ThemeToggle />);
  expect(screen.getByRole("radio", { name: "Dark" })).toHaveProperty("checked", true);
});
