export type ThemePreference = "system" | "light" | "dark";

export const THEME_KEY = "theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

export function readThemePreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

function resolve(preference: ThemePreference): "light" | "dark" {
  if (preference !== "system") {
    return preference;
  }
  return window.matchMedia?.(DARK_QUERY).matches ? "dark" : "light";
}

// Every color transition firing at once smears the switch, so transitions are
// off for the frame the theme changes in.
export function applyTheme(preference: ThemePreference) {
  const root = document.documentElement;
  const next = resolve(preference);
  if (root.dataset.theme === next) {
    return;
  }
  const pause = document.createElement("style");
  pause.textContent = "*,*::before,*::after{transition:none!important}";
  document.head.appendChild(pause);
  root.dataset.theme = next;
  void getComputedStyle(root).colorScheme;
  requestAnimationFrame(() => pause.remove());
}

export function saveThemePreference(preference: ThemePreference) {
  try {
    if (preference === "system") {
      localStorage.removeItem(THEME_KEY);
    } else {
      localStorage.setItem(THEME_KEY, preference);
    }
  } catch {
    // Private mode can refuse storage. The choice still holds for this page.
  }
  applyTheme(preference);
}

// Runs in <head> before first paint, so a dark page never flashes light, and
// keeps following the system while no explicit choice is stored.
export const themeScript = `(function(){var q=matchMedia(${JSON.stringify(DARK_QUERY)});function s(){var t;try{t=localStorage.getItem(${JSON.stringify(THEME_KEY)})}catch(e){}if(t!=="light"&&t!=="dark")t=q.matches?"dark":"light";document.documentElement.dataset.theme=t}s();q.addEventListener("change",s)})()`;
