import type { LucideIcon } from "lucide-react";
import { FilePenLine, Search, Settings } from "lucide-react";

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
        { title: "Profile Builder", url: "/profile-builder", icon: FilePenLine },
        { title: "Settings", url: "/settings", icon: Settings },
      ],
    },
  ];
}

export function titleFromPathname(pathname: string): string {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  if (normalized === "/analyze") return "Analyze";
  if (normalized === "/profile-builder") return "Profile Builder";
  if (normalized === "/settings") return "Settings";
  return "CV Analyzer";
}
