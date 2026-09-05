"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { PageBackToolbar } from "@/components/layout/page-back-toolbar";
import { useCopy } from "@/lib/app-settings";

type Member = { email: string; role: "owner" | "reviewer" };

export function FeedbackAccess() {
  const { t } = useCopy();
  const [members, setMembers] = useState<Member[]>([]);
  const [collectionEnabled, setCollectionEnabled] = useState(true);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Member["role"]>("reviewer");
  const [error, setError] = useState("");
  const [confirmRevoke, setConfirmRevoke] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    const response = await fetch("/api/feedback/access", { cache: "no-store" });
    if (!response.ok) throw new Error("feedback_access_unavailable");
    const data = await response.json();
    setMembers(data.members);
    setCollectionEnabled(data.collectionEnabled);
  }

  useEffect(() => {
    let active = true;
    fetch("/api/feedback/access", { cache: "no-store" })
      .then(async response => {
        if (!response.ok) throw new Error("feedback_access_unavailable");
        return response.json();
      })
      .then(data => {
        if (!active) return;
        setMembers(data.members);
        setCollectionEnabled(data.collectionEnabled);
      })
      .catch(() => { if (active) setError(t("feedbackAccessLoadFailed")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [t]);


  function accessError(code: string) {
    if (code === "email_domain_not_allowed") return t("feedbackDomainNotAllowed");
    if (code === "last_owner_protected") return t("lastOwnerProtected");
    if (code === "Forbidden") return t("feedbackAccessForbidden");
    return t("feedbackAccessUpdateFailed");
  }

  async function grant() {
    if (busy) return;
    setError("");
    setBusy(true);
    try {
      const response = await fetch("/api/feedback/access", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, role }),
      });
      if (!response.ok) { setError(accessError((await response.json()).error)); return; }
      setEmail("");
      await load();
    } catch {
      setError(t("feedbackAccessUpdateFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(memberEmail: string) {
    if (confirmRevoke !== memberEmail) {
      setConfirmRevoke(memberEmail);
      return;
    }
    if (busy) return;
    setError("");
    setConfirmRevoke(null);
    setBusy(true);
    try {
      const response = await fetch("/api/feedback/access", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: memberEmail }),
      });
      if (!response.ok) { setError(accessError((await response.json()).error)); return; }
      await load();
    } catch {
      setError(t("feedbackAccessUpdateFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function toggleCollection() {
    if (busy) return;
    const next = !collectionEnabled;
    setError("");
    setBusy(true);
    try {
      const response = await fetch("/api/feedback/access", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ collectionEnabled: next }),
      });
      if (!response.ok) { setError(t("feedbackAccessUpdateFailed")); return; }
      setCollectionEnabled(next);
    } catch {
      setError(t("feedbackAccessUpdateFailed"));
    } finally {
      setBusy(false);
    }
  }

  return <section className="mx-auto w-full max-w-[1800px]">
    <PageBackToolbar href="/feedback" />
    <div className="mx-auto max-w-6xl space-y-6">
      <div><h1 className="text-2xl font-semibold">{t("feedbackAccess")}</h1><p className="text-sm text-muted-foreground">{t("feedbackAccessDescription")}</p></div>
      <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
        <div><p className="font-medium">{t("feedbackCollection")}</p><p className="text-sm text-muted-foreground">{t("feedbackCollectionDescription")}</p></div>
        <button type="button" role="switch" aria-checked={collectionEnabled} disabled={busy || loading} onClick={() => void toggleCollection()} className={`shrink-0 rounded-full px-4 py-2 text-sm disabled:cursor-wait disabled:opacity-60 ${collectionEnabled ? "bg-primary text-primary-foreground" : "border"}`}>{t(collectionEnabled ? "enabled" : "disabled")}</button>
      </div>
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
        <input className="h-10 min-w-0 rounded-md border px-3" value={email} onChange={event => setEmail(event.target.value)} placeholder={t("companyEmail")} aria-label={t("companyEmail")} autoComplete="email" />
        <select className="h-10 rounded-md border bg-background px-3" value={role} onChange={event => setRole(event.target.value as Member["role"])} aria-label={t("feedbackAccess")}><option value="reviewer">{t("reviewer")}</option><option value="owner">{t("owner")}</option></select>
        <Button className="w-full sm:w-auto" onClick={() => void grant()} disabled={!email.trim() || busy || loading}>{t("grantAccess")}</Button>
      </div>
      {loading ? <p role="status" className="text-sm text-muted-foreground">{t("loadingFeedbackAccess")}</p> : null}
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
      <ul className="divide-y rounded-lg border">{members.map(member => {
        const awaitingConfirmation = confirmRevoke === member.email;
        return <li key={member.email} className="flex min-w-0 items-center justify-between gap-3 p-3">
          <span className="min-w-0 break-all text-sm sm:break-normal">{member.email} · {t(member.role)}</span>
          <Button
            variant={awaitingConfirmation ? "destructive" : "outline"}
            size="sm"
            className={awaitingConfirmation ? undefined : "border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"}
            onBlur={() => setConfirmRevoke(null)}
            onKeyDown={(event) => { if (event.key === "Escape") setConfirmRevoke(null); }}
            disabled={busy || loading}
            onClick={() => void revoke(member.email)}
          >
            {t(awaitingConfirmation ? "clickAgainToConfirm" : "revokeAccess")}
          </Button>
        </li>;
      })}</ul>
    </div>
  </section>;
}
