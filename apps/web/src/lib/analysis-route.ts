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
  url.searchParams.delete(RETURN_PARAM);
  url.hash = "";
  return url.toString();
}

const RETURN_PARAM = "from";
export const ANALYSES_RETURN = "analyses";

/** Analyze-page href that opens one report and remembers it was opened from the Analyses page. */
export function analyzeHrefFromAnalyses(analysisId: string): string {
  return `/analyze?analysis=${encodeURIComponent(analysisId)}&${RETURN_PARAM}=${ANALYSES_RETURN}`;
}

/** Where Back should lead after closing a report: the Analyses page, or null for the analyze page itself. */
export function analysisReturnPath(href: string): string | null {
  return new URL(href).searchParams.get(RETURN_PARAM) === ANALYSES_RETURN ? "/analyses" : null;
}

export function relativeHref(href: string): string {
  const url = new URL(href);
  return `${url.pathname}${url.search}${url.hash}`;
}
