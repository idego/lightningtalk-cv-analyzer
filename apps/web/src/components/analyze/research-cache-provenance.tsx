import type { ResearchCacheProvenance } from "@/lib/analyze-types";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";

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
    <HoverDisclosure
      className="ml-2 text-xs text-muted-foreground"
      triggerClassName="w-fit flex-none font-medium text-foreground"
      title={label}
      contentClassName="pl-3 pt-2"
    >
      <ul className="space-y-1">
        {cachedSubjects.map((subject) => (
          <li key={subject.normalized_subject}>
            {subject.normalized_subject}
            {subject.accessed_at ? ` · ${new Date(subject.accessed_at).toLocaleString(locale)}` : ""}
          </li>
        ))}
      </ul>
    </HoverDisclosure>
  );
}
