"use client";

import { useState } from "react";
import type { AnalysisReport, LinkedInComparison, LinkedInDiscovery } from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type State = "idle" | "pending" | "error" | "timeout" | "completed";

export function LinkedInResearchPanel({ report }: { report: AnalysisReport }) {
  const [discovery, setDiscovery] = useState<LinkedInDiscovery | undefined>(report.linkedin_discovery);
  const [comparison, setComparison] = useState<LinkedInComparison | undefined>(report.linkedin_comparison);
  const [confirmed, setConfirmed] = useState<string | null>(report.linkedin_comparison?.profile_url ?? null);
  const [discoveryState, setDiscoveryState] = useState<State>(discovery ? "completed" : "idle");
  const [comparisonState, setComparisonState] = useState<State>(comparison ? "completed" : "idle");
  const [error, setError] = useState<string | null>(null);
  const enabled = report.ai_analysis.status === "succeeded" && report.ai_analysis.research_candidates.some((item) => item.category === "linkedin");

  async function post(path: string, body: Record<string, unknown> = {}) {
    const response = await fetch(`/api/analyses/${encodeURIComponent(report.analysis_id)}/research/linkedin/${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ accessToken: report.analysis_access_token, ...body }) });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw Object.assign(new Error(payload.detail ?? payload.error ?? "linkedin_research_failed"), { timeout: response.status === 504 });
    return payload;
  }

  async function discover() { setDiscoveryState("pending"); setError(null); try { const payload=await post("discovery"); setDiscovery(payload.linkedin_discovery); setDiscoveryState("completed"); } catch (cause) { const timed=(cause as {timeout?:boolean}).timeout; setDiscoveryState(timed ? "timeout" : "error"); setError(timed ? "Discovery przekroczyło limit czasu. Retry jest bezpieczny." : (cause as Error).message); } }
  async function confirm(profileUrl: string) { setError(null); try { await post("confirmation", { profile_url: profileUrl }); setConfirmed(profileUrl); } catch (cause) { setError((cause as Error).message); } }
  async function compare() { setComparisonState("pending"); setError(null); try { const payload=await post("comparison"); setComparison(payload.linkedin_comparison); setComparisonState("completed"); } catch (cause) { const timed=(cause as {timeout?:boolean}).timeout; setComparisonState(timed ? "timeout" : "error"); setError(timed ? "Comparison przekroczyło limit czasu. Retry jest bezpieczny." : (cause as Error).message); } }

  return <section className="space-y-3 rounded-md border border-sky-500/30 p-3">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-medium">LinkedIn: discovery → confirmation → comparison</h3><p className="text-xs text-muted-foreground">Tylko możliwe publiczne profile. Ten workflow nie ustala tożsamości i nie zmienia score ani bandu.</p></div><Button type="button" variant="outline" onClick={discover} disabled={!enabled || discoveryState === "pending" || discoveryState === "completed"}>{discoveryState === "pending" ? "Discovering…" : discovery ? "Discovery completed" : "Start discovery"}</Button></div>
    {!enabled ? <p className="text-sm text-muted-foreground">Disabled: analiza nie zwróciła bezpiecznego candidate-scoped LinkedIn research candidate.</p> : null}
    {error ? <p className="text-sm text-destructive">{error}</p> : null}
    {discovery?.linkedin_not_found ? <div className="rounded border border-amber-500/30 p-2 text-sm"><Badge variant="outline">linkedin_not_found</Badge><p className="mt-2">{discovery.not_found_caveat}</p></div> : null}
    {discovery?.outcome === "ambiguous" ? <Badge variant="outline">ambiguous — recruiter decision required</Badge> : null}
    {discovery?.possible_profiles.map((profile) => <article key={profile.profile_url} className="space-y-2 rounded-md bg-muted/20 p-3 text-sm"><div className="flex flex-wrap items-center gap-2"><a href={profile.profile_url} target="_blank" rel="noreferrer" className="underline">Possible profile</a><Badge variant="outline">confidence: {profile.confidence}</Badge><Badge variant="outline">photo visible: {profile.photo_visible}</Badge><Badge variant="outline">connections: {profile.connection_count.display ?? "unknown"}</Badge>{profile.connection_completeness_flag ? <Badge variant="outline">completeness review</Badge> : null}</div><p className="text-xs text-muted-foreground">{profile.uncertainty}</p>{profile.match_evidence.map((item, i)=><div key={`${item.field}-${i}`} className="text-xs"><p>Match evidence · {item.field}: {item.cv_value} ↔ {item.profile_value}</p>{item.source_urls.map(url=><a key={url} href={url} target="_blank" rel="noreferrer" className="mr-2 underline">Source</a>)}</div>)}{profile.conflicts.map((item, i)=><div key={`${item.field}-${i}`} className="text-xs text-amber-700"><p>Conflict for review · {item.summary}</p>{item.source_urls.map(url=><a key={url} href={url} target="_blank" rel="noreferrer" className="mr-2 underline">Source</a>)}</div>)}{profile.photo_source_url ? <a href={profile.photo_source_url} target="_blank" rel="noreferrer" className="text-xs underline">Photo visibility source</a> : null}{profile.connection_count.source_url ? <a href={profile.connection_count.source_url} target="_blank" rel="noreferrer" className="ml-2 text-xs underline">Connection count source</a> : null}<Button type="button" size="sm" variant="outline" disabled={Boolean(confirmed)} onClick={()=>confirm(profile.profile_url)}>{confirmed === profile.profile_url ? "Confirmed for comparison" : "Confirm this URL for comparison"}</Button></article>)}
    {discovery ? <details className="text-xs text-muted-foreground"><summary>Searches and limitations</summary>{discovery.searches_performed.map(x=><p key={x}>Search: {x}</p>)}{discovery.search_limitations.map(x=><p key={x}>Limit: {x}</p>)}</details> : null}
    <div className="border-t pt-3"><Button type="button" variant="outline" onClick={compare} disabled={!confirmed || comparisonState === "pending" || comparisonState === "completed"}>{comparisonState === "pending" ? "Comparing…" : comparison ? "Comparison completed" : "Compare confirmed profile to CV"}</Button>{comparisonState === "timeout" || comparisonState === "error" ? <p className="mt-2 text-sm text-destructive">{error}</p> : null}</div>
    {comparison?.comparisons.map(item=><article key={item.field} className="rounded bg-muted/20 p-2 text-sm"><strong>{item.field}</strong> <Badge variant="outline">{item.status}</Badge><p>{item.cv_value ?? "CV unknown"} ↔ {item.profile_value ?? "profile unknown"}</p><p>{item.summary}</p><p className="text-xs text-muted-foreground">{item.uncertainty}</p>{item.source_urls.map(url=><a key={url} href={url} target="_blank" rel="noreferrer" className="mr-2 text-xs underline">Source</a>)}</article>)}
    {comparison ? <details className="text-xs text-muted-foreground"><summary>Comparison searches and limitations</summary>{comparison.searches_performed.map(x=><p key={x}>Search: {x}</p>)}{comparison.limitations.map(x=><p key={x}>Limit: {x}</p>)}</details> : null}
  </section>;
}
