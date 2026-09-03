import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { requireWebUser } from "@/lib/web-user";

export default async function AppLayout({ children }: { children: ReactNode }) {
  await requireWebUser();
  return <AppShell>{children}</AppShell>;
}
