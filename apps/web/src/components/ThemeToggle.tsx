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
      className="inline-flex min-h-9 items-center gap-2 rounded-full border border-rule px-3 py-1.5 text-caption text-muted transition-colors hover:text-ink"
      onClick={() => {
        setTheme(theme === "dark" ? "light" : "dark");
      }}
      aria-label={`Current theme ${theme}. Switch to ${theme === "dark" ? "light" : "dark"} theme`}
    >
      <span
        aria-hidden="true"
        className={`inline-block h-3 w-3 rounded-full border border-ink ${
          theme === "dark" ? "bg-ink" : "bg-transparent"
        }`}
      />
      {theme === "dark" ? "Dark" : "Light"}
    </button>
  );
}
