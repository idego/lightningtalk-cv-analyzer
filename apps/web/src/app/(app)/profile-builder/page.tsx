import { redirect } from "next/navigation";
import { ProfileBuilderWorkspace } from "@/components/profile-builder/profile-builder-workspace";
import { PROFILE_BUILDER_ENABLED } from "@/lib/feature-flags";

export default function ProfileBuilderPage() {
  if (!PROFILE_BUILDER_ENABLED) redirect("/analyze");
  return <ProfileBuilderWorkspace />;
}
