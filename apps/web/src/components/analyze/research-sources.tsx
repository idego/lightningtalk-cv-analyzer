import { ExternalLink } from "lucide-react";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";

export function ResearchSources({ urls }: { urls: Array<string | null | undefined> }) {
  const sources = Array.from(new Set(urls.filter((url): url is string => Boolean(url))));
  if (!sources.length) return null;

  return (
    <HoverDisclosure
      className="text-xs"
      triggerClassName="w-fit flex-none font-medium text-foreground"
      title={`View sources (${sources.length})`}
      contentClassName="pt-2"
    >
      <ul className="space-y-1.5">
        {sources.map((url, index) => (
          <li key={url}>
            <a
              href={url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex max-w-full items-center gap-1 text-muted-foreground underline underline-offset-2 hover:text-foreground"
            >
              <span className="truncate">Source {index + 1}</span>
              <ExternalLink aria-hidden="true" className="size-3 shrink-0" />
            </a>
          </li>
        ))}
      </ul>
    </HoverDisclosure>
  );
}
