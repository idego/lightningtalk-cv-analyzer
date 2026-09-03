"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
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

  async function load() {
    const response = await fetch("/api/feedback/access", { cache: "no-store" });
    if (!response.ok) return;
    const data = await response.json();
    setMembers(data.members);
    setCollectionEnabled(data.collectionEnabled);
  }

  useEffect(() => {
    let active = true;
    fetch("/api/feedback/access", { cache: "no-store" })
      .then(async response => response.ok ? response.json() : null)
      .then(data => {
        if (!active || !data) return;
        setMembers(data.members);
        setCollectionEnabled(data.collectionEnabled);
      });
    return () => { active = false; };
  }, []);

  async function grant() {
    setError("");
    const response = await fetch("/api/feedback/access", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, role }),
    });
    if (!response.ok) { setError((await response.json()).error); return; }
    setEmail("");
    await load();
  }

  async function revoke(memberEmail: string) {
    if (confirmRevoke !== memberEmail) {
      setConfirmRevoke(memberEmail);
      return;
    }
    setError("");
    setConfirmRevoke(null);
    const response = await fetch("/api/feedback/access", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: memberEmail }),
    });
    if (!response.ok) { setError((await response.json()).error); return; }
    await load();
  }

  async function toggleCollection() {
    const next = !collectionEnabled;
    const response = await fetch("/api/feedback/access", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ collectionEnabled: next }),
    });
    if (response.ok) setCollectionEnabled(next);
  }

  return <section className="mx-auto max-w-6xl space-y-6">
    <div className="space-y-3">
      <Button variant="outline" nativeButton={false} className="w-fit" render={<Link href="/feedback"><ArrowLeft data-icon="inline-start" />{t("back")}</Link>} />
      <div><h1 className="text-2xl font-semibold">{t("feedbackAccess")}</h1><p className="text-sm text-muted-foreground">{t("feedbackAccessDescription")}</p></div>
    </div>
    <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
      <div><p className="font-medium">{t("feedbackCollection")}</p><p className="text-sm text-muted-foreground">{t("feedbackCollectionDescription")}</p></div>
      <button type="button" role="switch" aria-checked={collectionEnabled} onClick={toggleCollection} className={`shrink-0 rounded-full px-4 py-2 text-sm ${collectionEnabled ? "bg-primary text-primary-foreground" : "border"}`}>{t(collectionEnabled ? "enabled" : "disabled")}</button>
    </div>
    <div className="flex gap-2">
      <input className="flex-1 rounded-md border px-3" value={email} onChange={event => setEmail(event.target.value)} placeholder={t("companyEmail")} aria-label={t("companyEmail")} />
      <select className="rounded-md border px-3" value={role} onChange={event => setRole(event.target.value as Member["role"])} aria-label={t("feedbackAccess")}><option value="reviewer">{t("reviewer")}</option><option value="owner">{t("owner")}</option></select>
      <button className="rounded-md bg-primary px-4 py-2 text-primary-foreground" onClick={grant}>{t("grantAccess")}</button>
    </div>
    {error ? <p className="text-sm text-destructive">{error}</p> : null}
    <ul className="divide-y rounded-lg border">{members.map(member => {
      const awaitingConfirmation = confirmRevoke === member.email;
      return <li key={member.email} className="flex items-center justify-between p-3">
        <span>{member.email} · {t(member.role)}</span>
        <Button
          variant={awaitingConfirmation ? "destructive" : "ghost"}
          size="sm"
          className={awaitingConfirmation ? undefined : "text-destructive hover:text-destructive"}
          onBlur={() => setConfirmRevoke(null)}
          onKeyDown={(event) => { if (event.key === "Escape") setConfirmRevoke(null); }}
          onClick={() => void revoke(member.email)}
        >
          {t(awaitingConfirmation ? "clickAgainToConfirm" : "revokeAccess")}
        </Button>
      </li>;
    })}</ul>
  </section>;
}
