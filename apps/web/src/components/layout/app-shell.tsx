"use client";

import type { ReactNode } from "react";
import { SidebarProvider } from "@/components/ui/sidebar";
import { usePathname } from "next/navigation";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppHeader } from "@/components/layout/app-header";
import { SiteFooter } from "@/components/layout/site-footer";
import { buildSidebarNav } from "@/components/layout/sidebar-data";
import type { FeedbackRole } from "@/lib/feedback-access";

type AppShellProps = {
  defaultOpen?: boolean;
  children: ReactNode;
  feedbackRole?: FeedbackRole | null;
};

export function AppShell({ defaultOpen = true, children, feedbackRole }: AppShellProps) {
  const nav = buildSidebarNav(Boolean(feedbackRole));

  const templateEditor = usePathname().startsWith("/profile-builder/templates/");
  return (
    <SidebarProvider defaultOpen={defaultOpen} className="min-h-dvh w-full">
      <AppSidebar nav={nav} />
      <div id="content" className="bg-background flex h-svh min-w-0 flex-1 flex-col overflow-y-auto">
        <AppHeader />
        <main className={`w-full flex-1 px-4 md:px-6 ${templateEditor ? "min-h-0 overflow-hidden py-4" : "py-6"}`}>
          {children}
        </main>
        {!templateEditor ? <SiteFooter /> : null}
      </div>
    </SidebarProvider>
  );
}
