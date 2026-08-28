import { ProfileTemplateCreator } from "@/components/profile-builder/profile-template-creator";

export default async function ProfileTemplatePage({
  params,
  searchParams,
}: {
  params: Promise<{ templateId: string }>;
  searchParams: Promise<{ profile?: string }>;
}) {
  const [{ templateId }, query] = await Promise.all([params, searchParams]);
  return (
    <ProfileTemplateCreator
      templateId={templateId === "new" ? null : templateId}
      returnProfileId={query.profile ?? null}
    />
  );
}
