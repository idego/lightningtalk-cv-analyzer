"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCopy } from "@/lib/app-settings";

type PageBackToolbarProps = {
  href?: string;
  onBack?: () => void;
  detail?: ReactNode;
  action?: ReactNode;
};

export function PageBackToolbar({ href, onBack, detail, action }: PageBackToolbarProps) {
  const { t } = useCopy();
  const backButton = href ? (
    <Button
      variant="outline"
      nativeButton={false}
      render={<Link href={href}><ArrowLeft data-icon="inline-start" />{t("back")}</Link>}
    />
  ) : onBack ? (
    <Button variant="outline" onClick={onBack}>
      <ArrowLeft data-icon="inline-start" />
      {t("back")}
    </Button>
  ) : null;

  return (
    <div className="mb-3 flex min-h-10 items-start justify-between gap-4">
      <div className="flex items-center gap-4">
        {backButton}
        {detail}
      </div>
      {action}
    </div>
  );
}
