import type { ResearchCacheProvenance } from "@/lib/analyze-types";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";

/** Cache provenance for a research section: a collapsed "Cached result" disclosure listing the cached subjects. */
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
  if (!cachedSubjects.length) return <p className="ml-2 text-xs text-muted-foreground">{label}</p>;
  return (
    <HoverDisclosure className="ml-2 text-xs text-muted-foreground" triggerClassName="w-fit flex-none" title={label} contentClassName="space-y-1 pl-3 pt-2">
      {cachedSubjects.map((subject) => (
        <p key={subject.normalized_subject}>
          {subject.normalized_subject}
          {subject.accessed_at ? ` · ${new Date(subject.accessed_at).toLocaleString(locale)}` : ""}
        </p>
      ))}
    </HoverDisclosure>
  );
}
