import { ExternalLink } from "lucide-react";

export function ResearchSources({ urls }: { urls: Array<string | null | undefined> }) {
  const sources = Array.from(new Set(urls.filter((url): url is string => Boolean(url))));
  if (!sources.length) return null;

  return (
    <details className="text-xs">
      <summary className="w-fit cursor-pointer font-medium text-foreground">
        View sources ({sources.length})
      </summary>
      <ul className="mt-2 space-y-1.5">
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
    </details>
  );
}
