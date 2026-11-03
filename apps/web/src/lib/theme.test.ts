import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { saveThemePreference, themeScript, THEME_KEY } from "@/lib/theme";

// A system color scheme the test can flip, like the OS setting.
function stubSystem(dark: boolean) {
  const listeners = new Set<() => void>();
  const query = {
    matches: dark,
    addEventListener: (_: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
  };
  vi.stubGlobal("matchMedia", () => query);
  return (next: boolean) => {
    query.matches = next;
    for (const listener of listeners) {
      listener();
    }
  };
}

const theme = () => document.documentElement.dataset.theme;

beforeEach(() => {
  localStorage.clear();
  document.documentElement.dataset.theme = "light";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

test("the head script follows the system when nothing is stored", () => {
  const setSystem = stubSystem(true);
  new Function(themeScript)();
  expect(theme()).toBe("dark");

  setSystem(false);
  expect(theme()).toBe("light");
});

test("the head script keeps a stored choice over the system", () => {
  const setSystem = stubSystem(true);
  localStorage.setItem(THEME_KEY, "light");
  new Function(themeScript)();
  expect(theme()).toBe("light");

  setSystem(true);
  expect(theme()).toBe("light");
});

test("choosing a theme stores it, and system clears it", () => {
  stubSystem(true);
  saveThemePreference("light");
  expect(theme()).toBe("light");
  expect(localStorage.getItem(THEME_KEY)).toBe("light");

  saveThemePreference("system");
  expect(theme()).toBe("dark");
  expect(localStorage.getItem(THEME_KEY)).toBeNull();
});
