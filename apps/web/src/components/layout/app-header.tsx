"use client";

import { usePathname } from "next/navigation";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { SignOutButton } from "@/components/auth/sign-out-button";
import { titleFromPathname } from "@/components/layout/sidebar-data";

export function AppHeader() {
  const pathname = usePathname();
  const title = titleFromPathname(pathname);

  return (
    <header className="sticky top-0 z-30 flex w-full min-w-0 items-center gap-2 border-b bg-background/85 px-4 py-3 backdrop-blur sm:gap-3 sm:px-6">
      <SidebarTrigger className="size-8 shrink-0" />
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-base font-medium">{title}</h1>
      </div>
      <div className="ml-auto flex shrink-0 items-center gap-1">
        <ThemeToggle />
        <SignOutButton />
      </div>
    </header>
  );
}
