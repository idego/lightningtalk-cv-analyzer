import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { requireWebUser } from "@/lib/web-user";
import { feedbackRole } from "@/lib/feedback-access";

export default async function AppLayout({ children }: { children: ReactNode }) {
  const user=await requireWebUser();
  return <AppShell feedbackRole={feedbackRole(user.id)}>{children}</AppShell>;
}
