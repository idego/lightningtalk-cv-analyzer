"use client";

import { useEffect } from "react";

function readCookieTheme(): string | null {
  const m = document.cookie.match(/(?:^|; )theme=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

export function ThemeBootstrap() {
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("theme") ?? readCookieTheme();
      const isDark = stored
        ? stored === "dark"
        : window.matchMedia("(prefers-color-scheme: dark)").matches;
      document.documentElement.classList.toggle("dark", isDark);
    } catch {
      // Ignore restricted environments.
    }
  }, []);

  return null;
}
