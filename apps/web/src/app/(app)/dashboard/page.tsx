import { DashboardPanel } from "@/components/dashboard/dashboard-panel";
import { feedbackRole } from "@/lib/feedback-access";
import { requireWebUser } from "@/lib/web-user";

export default async function DashboardPage() {
  const user = await requireWebUser();
  return <DashboardPanel feedbackRole={feedbackRole(user.email)} />;
}
