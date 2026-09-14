import { redirect } from "next/navigation";
import { ProfileTemplateCreator } from "@/components/profile-builder/profile-template-creator";
import { PROFILE_BUILDER_ENABLED } from "@/lib/feature-flags";

export default async function ProfileTemplatePage({
  params,
  searchParams,
}: {
  params: Promise<{ templateId: string }>;
  searchParams: Promise<{ profile?: string }>;
}) {
  if (!PROFILE_BUILDER_ENABLED) redirect("/analyze");
  const [{ templateId }, query] = await Promise.all([params, searchParams]);
  return (
    <ProfileTemplateCreator
      templateId={templateId === "new" ? null : templateId}
      returnProfileId={query.profile ?? null}
    />
  );
}
