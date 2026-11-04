import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { AppShell } from "@/components/app-shell";

const pathname = vi.hoisted(() => ({ current: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => pathname.current }));

beforeEach(() => {
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

function renderShell() {
  render(
    <AppShell account={<button type="button">Sign out</button>}>
      <main>Page</main>
    </AppShell>,
  );
}

test("shell starts with a skip link and names its navigation", () => {
  renderShell();

  expect(screen.getAllByRole("link")[0]?.textContent).toBe("Skip to content");
  expect(screen.getByRole("link", { name: "Skip to content" }).getAttribute("href")).toBe("#content");
  expect(screen.getByRole("navigation", { name: "Main" })).toBeDefined();
  expect(screen.getByRole("link", { name: "Products" }).getAttribute("href")).toBe("/");
  expect(screen.getByRole("group", { name: "Theme" })).toBeDefined();
  expect(screen.getByRole("button", { name: "Sign out" })).toBeDefined();
  expect(screen.getByRole("main").textContent).toBe("Page");
});

test("product pages mark Products as the current page", () => {
  pathname.current = "/products/11111111-1111-4111-8111-111111111111";
  renderShell();

  expect(screen.getByRole("link", { name: "Products" }).getAttribute("aria-current")).toBe("page");
  expect(screen.getByRole("link", { name: "Settings" }).getAttribute("aria-current")).toBeNull();
});

test("settings marks Settings as the current page", () => {
  pathname.current = "/settings";
  renderShell();

  expect(screen.getByRole("link", { name: "Settings" }).getAttribute("aria-current")).toBe("page");
  expect(screen.getByRole("link", { name: "Products" }).getAttribute("aria-current")).toBeNull();
});
