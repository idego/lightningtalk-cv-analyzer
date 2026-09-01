import type { ResearchCacheProvenance } from "@/lib/analyze-types";

export function ResearchCacheProvenanceView({
  cache,
  locale,
}: {
  cache: ResearchCacheProvenance | undefined;
  locale: "en" | "pl";
}) {
  if (!cache || cache.status === "miss") return null;
  const cachedSubjects = cache.subjects?.filter((subject) => subject.status === "hit") ?? [];
  const label = cache.status === "hit"
    ? (locale === "pl" ? "Wynik z cache" : "Cached result")
    : (locale === "pl" ? "Częściowo z cache" : "Partial cache hit");
  return (
    <div className="space-y-1 text-xs text-muted-foreground">
      <p>{label}</p>
      {cachedSubjects.map((subject) => (
        <p key={subject.normalized_subject}>
          {subject.normalized_subject}
          {subject.accessed_at ? ` · ${new Date(subject.accessed_at).toLocaleString(locale)}` : ""}
        </p>
      ))}
    </div>
  );
}
