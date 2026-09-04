"use client";

import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCopy } from "@/lib/app-settings";

export function ThemeToggle() {
  const { t } = useCopy();

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="size-8"
      onClick={() => {
        const isDark = document.documentElement.classList.toggle("dark");
        const theme = isDark ? "dark" : "light";
        window.localStorage.setItem("theme", theme);
        document.cookie = `theme=${theme}; path=/; max-age=31536000; samesite=lax`;
      }}
      aria-label={t("toggleTheme")}
      title={t("toggleTheme")}
    >
      <Sun className="hidden size-4 dark:block" />
      <Moon className="size-4 dark:hidden" />
    </Button>
  );
}
