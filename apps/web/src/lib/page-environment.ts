import { useSyncExternalStore } from "react";

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

function subscribeToReducedMotion(notify: () => void) {
  const query = window.matchMedia?.(REDUCED_MOTION);
  query?.addEventListener("change", notify);
  return () => query?.removeEventListener("change", notify);
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeToReducedMotion,
    () => window.matchMedia?.(REDUCED_MOTION).matches ?? false,
    () => false,
  );
}

export type PageTheme = "light" | "dark";

function subscribeToTheme(notify: () => void) {
  const watch = new MutationObserver(notify);
  watch.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme", "class"],
  });
  return () => watch.disconnect();
}

// The page sets its theme on <html>, which can differ from the system theme.
export function usePageTheme(): PageTheme {
  return useSyncExternalStore(
    subscribeToTheme,
    () => {
      const root = document.documentElement;
      return root.dataset.theme === "dark" || root.classList.contains("dark")
        ? "dark"
        : "light";
    },
    () => "light",
  );
}
