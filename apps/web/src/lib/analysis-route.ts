export type AnalysisRouteState = {
  analysisId: string | null;
  shareToken: string | null;
};

export function parseAnalysisRoute(href: string): AnalysisRouteState {
  const url = new URL(href);
  const fragment = new URLSearchParams(url.hash.startsWith("#") ? url.hash.slice(1) : url.hash);
  return {
    analysisId: url.searchParams.get("analysis"),
    shareToken: fragment.get("share"),
  };
}

export function withAnalysisRoute(href: string, analysisId: string, shareToken?: string | null): string {
  const url = new URL(href);
  url.searchParams.set("analysis", analysisId);
  url.hash = shareToken ? `share=${encodeURIComponent(shareToken)}` : "";
  return url.toString();
}

export function withoutAnalysisRoute(href: string): string {
  const url = new URL(href);
  url.searchParams.delete("analysis");
  url.hash = "";
  return url.toString();
}

export function relativeHref(href: string): string {
  const url = new URL(href);
  return `${url.pathname}${url.search}${url.hash}`;
}
