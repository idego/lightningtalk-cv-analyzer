"use client";

import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useCopy } from "@/lib/app-settings";

export function GoogleSearchAction({
  href,
  subject,
}: {
  href: string;
  subject?: string | null;
}) {
  const { t } = useCopy();
  const label = subject?.trim() ? t("searchSubjectWithGoogle", { subject: subject.trim() }) : t("searchWithGoogle");
  return (
    <Tooltip>
      <TooltipTrigger render={<Button variant="outline" size="icon-sm" className="active:scale-[0.92]" nativeButton={false} render={<a href={href} target="_blank" rel="noreferrer" aria-label={label}><Search aria-hidden /></a>} />} />
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
