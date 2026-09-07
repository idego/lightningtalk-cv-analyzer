import type { LucideIcon } from "lucide-react";
import { LayoutDashboard, MessageSquareText, Search, Settings, UserRoundPen } from "lucide-react";

export type NavItem = {
  title: string;
  url: string;
  icon?: LucideIcon;
};

export type NavGroup = {
  title: string;
  items: NavItem[];
};

export function buildSidebarNav(showFeedback = false): NavGroup[] {
  return [
    {
      title: "Analysis",
      items: [
        { title: "Analyze", url: "/analyze", icon: Search },
        { title: "Profile Builder", url: "/profile-builder", icon: UserRoundPen },
        { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
        ...(showFeedback ? [{ title: "Feedback", url: "/feedback", icon: MessageSquareText }] : []),
        { title: "Settings", url: "/settings", icon: Settings },
      ],
    },
  ];
}

export function isSidebarItemActive(pathname: string, itemUrl: string): boolean {
  const current = pathname.replace(/\/+$/, "") || "/";
  const target = itemUrl.replace(/\/+$/, "") || "/";
  if (target === "/profile-builder" && (current === "/profiles" || current.startsWith("/profiles/"))) return true;
  return current === target || (target !== "/" && current.startsWith(`${target}/`));
}

export function titleFromPathname(pathname: string): string {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  if (normalized === "/analyze") return "Analyze";
  if (normalized === "/dashboard") return "Dashboard";
  if (normalized.startsWith("/profile-builder/templates/")) return "Template Creator";
  if (normalized === "/profile-builder") return "Profile Builder";
  if (normalized === "/profiles") return "Profiles";
  if (normalized === "/settings") return "Settings";
  if (normalized.startsWith("/feedback")) return "Feedback";
  return "CV Analyzer";
}
