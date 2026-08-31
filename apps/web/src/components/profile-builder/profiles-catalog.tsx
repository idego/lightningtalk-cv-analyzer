"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { LoaderCircle, Search, Trash2, UserRoundPen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { RecentProfileItem } from "@/components/profile-builder/profile-builder-model";
import { deleteProfile as apiDeleteProfile, listProfiles } from "@/components/profile-builder/profile-builder-client";


export function ProfilesCatalog() {
  const [profiles, setProfiles] = useState<RecentProfileItem[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProfiles(await listProfiles());
    } catch {
      setError("Profiles could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return profiles;
    return profiles.filter((profile) => [profile.candidate_name, profile.source_filename, profile.template_name]
      .some((value) => value?.toLocaleLowerCase().includes(needle)));
  }, [profiles, query]);

  async function deleteProfile(profile: RecentProfileItem) {
    if (!window.confirm(`Delete ${profile.candidate_name ?? profile.source_filename}?`)) return;
    try {
      await apiDeleteProfile(profile.profile_id);
      setProfiles((current) => current.filter((item) => item.profile_id !== profile.profile_id));
    } catch {
      setError("Profile could not be deleted.");
    }
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><h2 className="text-2xl font-semibold tracking-tight">Profiles</h2><p className="mt-1 text-sm text-muted-foreground">Saved candidate profiles. Reopen the exact profile, anonymization, and template snapshot.</p></div>
        <Button render={<Link href="/profile-builder" />}><UserRoundPen />Convert CV</Button>
      </div>
      <div className="relative max-w-xl"><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" /><Input aria-label="Search profiles" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search candidate, filename, or template…" className="pl-9" /></div>
      {error ? <p className="rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</p> : null}
      <div className="overflow-hidden rounded-xl border bg-card">
        <div className="grid grid-cols-[minmax(180px,1.1fr)_minmax(160px,1fr)_minmax(140px,.8fr)_180px_72px] gap-3 border-b bg-muted/25 px-4 py-2 text-xs font-medium text-muted-foreground">
          <span>Candidate</span><span>Source</span><span>Template</span><span>Updated</span><span />
        </div>
        {loading ? <div className="flex items-center justify-center py-14"><LoaderCircle className="size-6 animate-spin text-muted-foreground" /></div> : null}
        {!loading && !filtered.length ? <p className="px-4 py-12 text-center text-sm text-muted-foreground">{query ? "No profiles match this search." : "No saved profiles yet."}</p> : null}
        {!loading && filtered.map((profile) => (
          <div key={profile.profile_id} className="grid grid-cols-[minmax(180px,1.1fr)_minmax(160px,1fr)_minmax(140px,.8fr)_180px_72px] items-center gap-3 border-b px-4 py-3 last:border-b-0">
            <Link href={`/profile-builder?profile=${encodeURIComponent(profile.profile_id)}`} className="min-w-0 font-medium hover:underline"><span className="block truncate">{profile.candidate_name ?? "Unnamed candidate"}</span></Link>
            <span className="truncate text-sm text-muted-foreground">{profile.source_filename}</span>
            <span className="truncate text-sm">{profile.template_name}</span>
            <time className="text-sm text-muted-foreground">{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(profile.updated_at))}</time>
            <Button variant="ghost" size="icon-sm" aria-label={`Delete ${profile.candidate_name ?? profile.source_filename}`} onClick={() => void deleteProfile(profile)}><Trash2 /></Button>
          </div>
        ))}
      </div>
    </div>
  );
}
