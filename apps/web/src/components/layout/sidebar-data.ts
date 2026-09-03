import type { LucideIcon } from "lucide-react";
import { LayoutDashboard, Search, Settings } from "lucide-react";

export type NavItem = {
  title: string;
  url: string;
  icon?: LucideIcon;
};

export type NavGroup = {
  title: string;
  items: NavItem[];
};

export function buildSidebarNav(): NavGroup[] {
  return [
    {
      title: "Analysis",
      items: [
        { title: "Analyze", url: "/analyze", icon: Search },
        { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
        { title: "Settings", url: "/settings", icon: Settings },
      ],
    },
  ];
}

export function isSidebarItemActive(pathname: string, itemUrl: string): boolean {
  const current = pathname.replace(/\/+$/, "") || "/";
  const target = itemUrl.replace(/\/+$/, "") || "/";
  return current === target || (target !== "/" && current.startsWith(`${target}/`));
}

export function titleFromPathname(pathname: string): string {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  if (normalized === "/analyze") return "Analyze";
  if (normalized === "/dashboard") return "Dashboard";
  if (normalized === "/settings") return "Settings";
  if (normalized.startsWith("/feedback")) return "Feedback";
  return "CV Analyzer";
}
