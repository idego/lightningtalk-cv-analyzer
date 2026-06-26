"use client";

import Link from "next/link";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import type { NavGroup } from "@/components/layout/sidebar-data";
import { IDEGO_LOGO_URL } from "@/lib/idego";

type AppSidebarProps = React.ComponentProps<typeof Sidebar> & {
  nav: NavGroup[];
};

export function AppSidebar({ nav, ...props }: AppSidebarProps) {
  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="relative z-10 border-b border-sidebar-border py-4 pl-6 pr-4 group-data-[collapsible=icon]:py-3 group-data-[collapsible=icon]:pl-3 group-data-[collapsible=icon]:pr-2">
        <Link
          href="/analyze"
          className="flex min-w-0 items-center gap-3 rounded-lg outline-none ring-sidebar-ring focus-visible:ring-2 group-data-[collapsible=icon]:justify-center"
        >
          <img
            src={IDEGO_LOGO_URL}
            alt="Idego"
            width={120}
            height={40}
            className="h-[1.6rem] w-auto max-w-40 shrink-0 object-contain object-left brightness-0 invert group-data-[collapsible=icon]:h-5 group-data-[collapsible=icon]:max-w-full"
            loading="eager"
            decoding="async"
          />
          <span
            aria-hidden
            className="h-6 w-px shrink-0 bg-sidebar-border group-data-[collapsible=icon]:hidden"
          />
          <div className="flex min-w-0 leading-tight group-data-[collapsible=icon]:hidden">
            <span className="truncate text-sm font-semibold text-primary">CV Analyzer</span>
          </div>
        </Link>
      </SidebarHeader>

      <SidebarContent className="relative z-10">
        {nav.map((group) => (
          <SidebarGroup key={group.title}>
            <SidebarGroupLabel>{group.title}</SidebarGroupLabel>
            <SidebarMenu>
              {group.items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton
                    render={
                      <Link href={item.url}>
                        {item.icon ? <item.icon /> : null}
                        <span>{item.title}</span>
                      </Link>
                    }
                  />
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter className="relative z-10 border-t border-sidebar-border px-5 py-4 text-xs text-sidebar-foreground">
        Idego Pulse
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
