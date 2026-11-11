"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

const STORAGE_KEY = "mnemos.theme";

export function initialTheme(): Theme {
  if (typeof window === "undefined") {
    return "light";
  }
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeToggle(): React.ReactNode {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    setTheme(initialTheme());
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  return (
    <button
      type="button"
      className="field-label flex min-h-9 items-center gap-2 rounded-none border border-rule px-2 py-1 transition-colors hover:bg-surface"
      onClick={() => {
        setTheme(theme === "dark" ? "light" : "dark");
      }}
      aria-label={`Current theme ${theme}. Switch to ${theme === "dark" ? "light" : "dark"} theme`}
    >
      <span aria-hidden="true" className="inline-block h-2.5 w-2.5 border border-ink">
        {theme === "dark" ? <span className="block h-full w-full bg-ink" /> : null}
      </span>
      {theme === "dark" ? "Dark" : "Light"}
    </button>
  );
}
