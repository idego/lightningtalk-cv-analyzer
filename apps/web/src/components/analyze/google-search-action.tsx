"use client";

import { Button } from "@/components/ui/button";
import { ProviderActionIcon } from "@/components/analyze/search-provider-icon";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useCopy } from "@/lib/app-settings";

export function GoogleSearchAction({ href }: { href: string }) {
  const { t } = useCopy();
  const label = t("searchWithGoogle");
  return (
    <Tooltip>
      <TooltipTrigger render={<Button variant="outline" size="icon-sm" className="active:scale-[0.92]" nativeButton={false} render={<a href={href} target="_blank" rel="noreferrer" aria-label={label}><ProviderActionIcon provider="google" /></a>} />} />
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
