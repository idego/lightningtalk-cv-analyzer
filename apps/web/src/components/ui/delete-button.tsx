"use client";

import { useState } from "react";
import { LoaderCircle, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCopy } from "@/lib/app-settings";

export function DeleteButton({ label, disabled = false, onDelete }: {
  label: string;
  disabled?: boolean;
  onDelete: () => Promise<void>;
}) {
  const { t } = useCopy();
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  return <div className="relative shrink-0">
    <Button variant={armed ? "destructive" : "ghost"} size="icon"
      className={`size-8 ${armed ? "" : "text-foreground hover:bg-destructive/10 hover:text-destructive"}`}
      disabled={disabled || busy} aria-label={armed ? t("clickAgainToConfirm") : label}
      onBlur={() => setArmed(false)}
      onKeyDown={(event) => { if (event.key === "Escape") setArmed(false); }}
      onClick={async () => {
        if (!armed) { setArmed(true); return; }
        setArmed(false);
        setBusy(true);
        try { await onDelete(); } finally { setBusy(false); }
      }}
    >
      {busy ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className={`size-4 ${armed ? "delete-confirm-shake" : ""}`} />}
    </Button>
    {armed ? <span role="status" className="absolute right-0 top-full z-20 mt-2 whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-xs text-background shadow-md">{t("clickAgainToConfirm")}</span> : null}
  </div>;
}
