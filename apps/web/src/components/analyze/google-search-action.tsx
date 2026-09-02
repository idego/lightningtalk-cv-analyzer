"use client";

import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useCopy } from "@/lib/app-settings";

export function GoogleSearchAction({
  href,
}: {
  href: string;
}) {
  const { t } = useCopy();
  return (
    <Tooltip>
      <TooltipTrigger render={<Button variant="outline" size="icon-sm" className="active:scale-[0.92]" nativeButton={false} render={<a href={href} target="_blank" rel="noreferrer" aria-label={t("searchWithGoogle")}><Search aria-hidden /></a>} />} />
      <TooltipContent>{t("searchWithGoogle")}</TooltipContent>
    </Tooltip>
  );
}
