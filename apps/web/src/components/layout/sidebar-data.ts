import type { LucideIcon } from "lucide-react";
import { Search, Settings, UsersRound, UserRoundPen } from "lucide-react";

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
        { title: "Profile Builder", url: "/profile-builder", icon: UserRoundPen },
        { title: "Profiles", url: "/profiles", icon: UsersRound },
        { title: "Settings", url: "/settings", icon: Settings },
      ],
    },
  ];
}

export function isNavItemActive(pathname: string, itemUrl: string): boolean {
  const current = pathname.replace(/\/+$/, "") || "/";
  const target = itemUrl.replace(/\/+$/, "") || "/";
  return current === target || (target !== "/" && current.startsWith(`${target}/`));
}

export function titleFromPathname(pathname: string): string {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  if (normalized === "/analyze") return "Analyze";
  if (normalized === "/profile-builder") return "Profile Builder";
  if (normalized === "/profiles") return "Profiles";
  if (normalized === "/settings") return "Settings";
  return "CV Analyzer";
}
