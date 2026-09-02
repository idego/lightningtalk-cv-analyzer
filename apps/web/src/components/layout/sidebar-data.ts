import type { LucideIcon } from "lucide-react";
import { MessageSquareText, Search, Settings } from "lucide-react";

export type NavItem = {
  title: string;
  url: string;
  icon?: LucideIcon;
};

export type NavGroup = {
  title: string;
  items: NavItem[];
};

export function buildSidebarNav(showFeedback=false): NavGroup[] {
  return [
    {
      title: "Analysis",
      items: [
        { title: "Analyze", url: "/analyze", icon: Search },
        { title: "Settings", url: "/settings", icon: Settings },
        ...(showFeedback?[{title:"Feedback",url:"/feedback",icon:MessageSquareText}]:[]),
      ],
    },
  ];
}

export function titleFromPathname(pathname: string): string {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  if (normalized === "/analyze") return "Analyze";
  if (normalized === "/settings") return "Settings";
  if (normalized.startsWith("/feedback")) return "Feedback";
  return "CV Analyzer";
}
