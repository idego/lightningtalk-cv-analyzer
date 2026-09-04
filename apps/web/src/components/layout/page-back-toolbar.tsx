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
  center?: ReactNode;
  action?: ReactNode;
};

export function PageBackToolbar({ href, onBack, detail, center, action }: PageBackToolbarProps) {
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
    <div className="mb-3 grid min-h-10 grid-cols-[minmax(0,1fr)_minmax(0,2fr)_minmax(0,1fr)] items-center gap-2 sm:gap-4">
      <div className="flex min-w-0 items-center gap-4 justify-self-start">
        {backButton}
        {detail}
      </div>
      <div className="min-w-0 justify-self-stretch">{center}</div>
      <div className="justify-self-end">{action}</div>
    </div>
  );
}
