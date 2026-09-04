import { UploadPanel } from "@/components/analyze/upload-panel";

export default async function AnalyzePage({
  searchParams,
}: {
  searchParams: Promise<{ analysis?: string | string[] }>;
}) {
  const params = await searchParams;
  const initialAnalysisId = typeof params.analysis === "string" ? params.analysis : null;
  return <UploadPanel initialAnalysisId={initialAnalysisId} />;
}
