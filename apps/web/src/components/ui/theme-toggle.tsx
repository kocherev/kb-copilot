"use client";

import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { useSyncExternalStore } from "react";

import {
  readThemePreference,
  saveThemePreference,
  type ThemePreference,
} from "@/lib/theme";

const options: { value: ThemePreference; label: string; Icon: LucideIcon }[] = [
  { value: "system", label: "System", Icon: Monitor },
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
];

const listeners = new Set<() => void>();

function subscribe(notify: () => void) {
  listeners.add(notify);
  window.addEventListener("storage", notify);
  return () => {
    listeners.delete(notify);
    window.removeEventListener("storage", notify);
  };
}

function choose(preference: ThemePreference) {
  saveThemePreference(preference);
  for (const notify of listeners) {
    notify();
  }
}

// Native radios: arrow keys move the choice, and each option keeps its name.
export function ThemeToggle() {
  const preference = useSyncExternalStore(
    subscribe,
    readThemePreference,
    () => "system" as const,
  );
  return (
    <fieldset className="flex shrink-0 items-center gap-0.5 rounded-full bg-surface-sunken p-0.5 shadow-ring">
      <legend className="sr-only">Theme</legend>
      {options.map(({ value, label, Icon }) => (
        <label
          key={value}
          title={label}
          className="grid size-7 cursor-pointer place-items-center rounded-full text-muted-foreground transition-[color,background-color,box-shadow] duration-150 ease-out hover:text-foreground has-checked:bg-surface has-checked:text-foreground has-checked:shadow-soft has-focus-visible:outline-2 has-focus-visible:outline-offset-1 has-focus-visible:outline-ring pointer-coarse:size-10"
        >
          <input
            type="radio"
            name="theme"
            value={value}
            checked={preference === value}
            onChange={() => choose(value)}
            className="sr-only"
          />
          <Icon aria-hidden className="size-4" />
          <span className="sr-only">{label}</span>
        </label>
      ))}
    </fieldset>
  );
}
