"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { LoaderCircle, Search, UserRoundPen, X } from "lucide-react";
import { DeleteButton } from "@/components/ui/delete-button";
import { Button } from "@/components/ui/button";
import { PageBackToolbar } from "@/components/layout/page-back-toolbar";
import { Input } from "@/components/ui/input";
import type { RecentProfileItem } from "@/components/profile-builder/profile-builder-model";
import { deleteProfile as apiDeleteProfile, listProfiles } from "@/components/profile-builder/profile-builder-client";


export function ProfilesCatalog() {
  const [profiles, setProfiles] = useState<RecentProfileItem[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
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
    const normalized = (value: string) => value.normalize("NFKD").replace(/\p{M}/gu, "").replace(/[łŁ]/g, "l").toLowerCase();
    const words = normalized(query).trim().split(/\s+/).filter(Boolean);
    return profiles.filter((profile) => {
      const text = normalized([profile.candidate_name, profile.source_filename, profile.template_name].filter(Boolean).join(" "));
      return words.every((word) => text.includes(word));
    });
  }, [profiles, query]);

  async function deleteProfile(profile: RecentProfileItem) {
    if (deletingId) return;
    setDeletingId(profile.profile_id);
    setError(null);
    try {
      await apiDeleteProfile(profile.profile_id);
      setProfiles((current) => current.filter((item) => item.profile_id !== profile.profile_id));
    } catch {
      setError("Profile could not be deleted.");
    } finally { setDeletingId(null); }
  }

  return (
    <section className="@container/profiles mx-auto w-full max-w-6xl space-y-5">
      <PageBackToolbar href="/profile-builder" />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <p className="text-sm text-muted-foreground">Your saved candidate profiles, ready to edit or export.</p>
        <Button nativeButton={false} render={<Link href="/profile-builder" />}><UserRoundPen />Convert CV</Button>
      </div>
      <div className="relative max-w-xl">
        <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input type="search" aria-label="Search profiles" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Escape") setQuery(""); }} placeholder="Search candidate, filename, or template…" className="pl-9 pr-9 [&::-webkit-search-cancel-button]:appearance-none" />
        {query ? <Button variant="ghost" size="icon-sm" className="absolute right-0 top-0" aria-label="Clear profile search" onClick={() => setQuery("")}><X /></Button> : null}
      </div>
      {error ? <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm"><span>{error}</span><Button variant="outline" size="sm" disabled={loading} onClick={() => void refresh()}>Retry</Button></div> : null}
      {query && !loading && !error ? <p role="status" className="text-xs text-muted-foreground">{filtered.length} of {profiles.length} profiles</p> : null}
      <div className="overflow-hidden rounded-xl border bg-card">
        {loading ? <div role="status" className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />Loading profiles…</div> : null}
        {!loading && !error && !filtered.length ? <p className="px-4 py-10 text-center text-sm text-muted-foreground">{query ? "No profiles match this search. Try another name or filename." : "No saved profiles yet. Convert a CV to get started."}</p> : null}
        {!loading ? <ul className="divide-y">{filtered.map((profile) => (
          <li key={profile.profile_id} className="flex min-w-0 items-center gap-2 px-3 py-2">
            <Link href={`/profile-builder?profile=${encodeURIComponent(profile.profile_id)}`} className="grid min-w-0 flex-1 gap-2 rounded-lg p-2 outline-none hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring @min-[700px]/profiles:grid-cols-[minmax(0,1fr)_minmax(0,.6fr)_auto]">
              <span className="min-w-0"><span className="block truncate text-sm font-medium">{profile.candidate_name ?? "Unnamed candidate"}</span><span className="mt-0.5 block truncate text-xs text-muted-foreground">{profile.source_filename}</span></span>
              <span className="self-center truncate text-xs text-muted-foreground">{profile.template_name}</span>
              <time dateTime={profile.updated_at} className="self-center text-xs text-muted-foreground">{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(profile.updated_at))}</time>
            </Link>
            <DeleteButton label={`Delete ${profile.candidate_name ?? profile.source_filename}`} disabled={deletingId !== null} onDelete={() => deleteProfile(profile)} />
          </li>
        ))}</ul> : null}
      </div>
    </section>
  );
}
