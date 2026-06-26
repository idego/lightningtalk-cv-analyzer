"use client";

import type { ReactNode } from "react";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppHeader } from "@/components/layout/app-header";
import { SiteFooter } from "@/components/layout/site-footer";
import { buildSidebarNav } from "@/components/layout/sidebar-data";

type AppShellProps = {
  defaultOpen?: boolean;
  children: ReactNode;
};

export function AppShell({ defaultOpen = true, children }: AppShellProps) {
  const nav = buildSidebarNav();

  return (
    <SidebarProvider defaultOpen={defaultOpen} className="min-h-dvh w-full">
      <AppSidebar nav={nav} />
      <div id="content" className="bg-background flex min-h-dvh min-w-0 flex-1 flex-col">
        <AppHeader />
        <main className="mx-auto w-full max-w-5xl px-4 py-6 md:px-6">{children}</main>
        <SiteFooter />
      </div>
    </SidebarProvider>
  );
}
