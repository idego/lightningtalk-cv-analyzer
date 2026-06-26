"use client";

import { usePathname } from "next/navigation";
import { ClipboardList } from "lucide-react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ThemeToggle } from "@/components/theme/theme-toggle";
import { SignOutButton } from "@/components/auth/sign-out-button";
import { Button } from "@/components/ui/button";
import { titleFromPathname } from "@/components/layout/sidebar-data";

export function AppHeader() {
  const pathname = usePathname();
  const title = titleFromPathname(pathname);

  return (
    <header className="sticky top-0 z-30 flex h-14 w-full min-w-0 items-center gap-2 border-b bg-background/85 px-4 py-0 backdrop-blur sm:gap-3 sm:px-6">
      <SidebarTrigger className="size-8 shrink-0" />
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-base font-medium">{title}</h1>
      </div>
      <div className="ml-auto flex shrink-0 items-center gap-1">
        <ThemeToggle />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-8"
          aria-label="Open feature list board"
          title="Open feature list board"
          onClick={() => {
            window.open("https://boards.s18i.io/boards/S3q9Xbo5w63D", "_blank", "noopener,noreferrer");
          }}
        >
          <ClipboardList className="size-4" />
        </Button>
        <SignOutButton />
      </div>
    </header>
  );
}
