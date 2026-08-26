"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import type { NavGroup } from "@/components/layout/sidebar-data";
import { IDEGO_LOGO_URL } from "@/lib/idego";
import { useCopy } from "@/lib/app-settings";

type AppSidebarProps = React.ComponentProps<typeof Sidebar> & {
  nav: NavGroup[];
};

export function AppSidebar({ nav, ...props }: AppSidebarProps) {
  const pathname = usePathname();
  const { t } = useCopy();

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="relative z-10 min-h-14 shrink-0 border-b border-sidebar-border p-4 group-data-[collapsible=icon]:p-3">
        <Link
          href="/analyze"
          className="flex min-w-0 items-center gap-3 rounded-lg outline-none ring-sidebar-ring focus-visible:ring-2 group-data-[collapsible=icon]:gap-0 group-data-[collapsible=icon]:justify-center"
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
            data-sidebar-motion="content"
            className="h-6 w-px shrink-0 bg-sidebar-border opacity-100 transition-[width,opacity,transform] duration-150 [transition-timing-function:var(--motion-ease-out)] group-data-[collapsible=icon]:w-0 group-data-[collapsible=icon]:-translate-x-1 group-data-[collapsible=icon]:opacity-0"
          />
          <div
            data-sidebar-motion="content"
            className="flex min-w-0 max-w-36 leading-tight opacity-100 transition-[max-width,opacity,transform] duration-150 [transition-timing-function:var(--motion-ease-out)] group-data-[collapsible=icon]:pointer-events-none group-data-[collapsible=icon]:max-w-0 group-data-[collapsible=icon]:-translate-x-1 group-data-[collapsible=icon]:opacity-0"
          >
            <span className="truncate text-sm font-semibold text-primary">CV Analyzer</span>
          </div>
        </Link>
      </SidebarHeader>

      <SidebarContent className="relative z-10">
        {nav.map((group) => (
          <SidebarGroup
            key={group.title}
            className="group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:p-1"
          >
            <SidebarMenu>
              {group.items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton
                    isActive={pathname.replace(/\/+$/, "") === item.url.replace(/\/+$/, "")}
                    tooltip={item.url === "/settings" ? t("settings") : t("analyze")}
                    className="group-data-[collapsible=icon]:size-10! group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:gap-0 group-data-[collapsible=icon]:p-0! [&>svg]:size-5!"
                    render={
                      <Link href={item.url}>
                        {item.icon ? <item.icon /> : null}
                        <span
                          data-sidebar-motion="content"
                          className="opacity-100 transition-[width,opacity,transform] duration-150 [transition-timing-function:var(--motion-ease-out)] group-data-[collapsible=icon]:pointer-events-none group-data-[collapsible=icon]:w-0 group-data-[collapsible=icon]:overflow-hidden group-data-[collapsible=icon]:-translate-x-1 group-data-[collapsible=icon]:opacity-0"
                        >
                          {item.url === "/settings" ? t("settings") : t("analyze")}
                        </span>
                      </Link>
                    }
                  />
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter className="relative z-10 min-h-12 overflow-hidden border-t border-sidebar-border px-5 py-4 text-xs text-sidebar-brand-light group-data-[collapsible=icon]:px-3">
        <span
          data-sidebar-motion="content"
          className="whitespace-nowrap opacity-100 transition-[opacity,transform] duration-150 [transition-timing-function:var(--motion-ease-out)] group-data-[collapsible=icon]:pointer-events-none group-data-[collapsible=icon]:-translate-x-1 group-data-[collapsible=icon]:opacity-0"
        >
          Idego Pulse
        </span>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
