"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
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
  const pathname = usePathname();
  const isTemplateCreator = pathname.startsWith("/profile-builder/templates/");

  return (
    <SidebarProvider defaultOpen={defaultOpen} className="min-h-dvh w-full">
      <AppSidebar nav={nav} />
      <div
        id="content"
        className={`bg-background flex h-svh min-w-0 flex-1 flex-col ${isTemplateCreator ? "overflow-hidden" : "overflow-y-auto"}`}
      >
        <AppHeader />
        <main className={isTemplateCreator ? "min-h-0 w-full flex-1 overflow-hidden p-3 md:p-4" : "w-full flex-1 px-4 py-6 md:px-6"}>
          {children}
        </main>
        {isTemplateCreator ? null : <SiteFooter />}
      </div>
    </SidebarProvider>
  );
}
