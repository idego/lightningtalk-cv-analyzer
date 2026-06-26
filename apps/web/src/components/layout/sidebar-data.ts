import type { LucideIcon } from "lucide-react";
import { Search } from "lucide-react";

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
      items: [{ title: "Analyze", url: "/analyze", icon: Search }],
    },
  ];
}

export function titleFromPathname(pathname: string): string {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  if (normalized === "/analyze") return "Analyze";
  return "CV Analyzer";
}
