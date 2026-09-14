import { redirect } from "next/navigation";
import { ProfilesCatalog } from "@/components/profile-builder/profiles-catalog";
import { PROFILE_BUILDER_ENABLED } from "@/lib/feature-flags";

export default function ProfilesPage() {
  if (!PROFILE_BUILDER_ENABLED) redirect("/analyze");
  return <ProfilesCatalog />;
}
