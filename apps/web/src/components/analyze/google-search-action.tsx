"use client";

import { ExternalLink, Search } from "lucide-react";
import { GoogleIcon } from "@/components/ui/google-icon";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useCopy } from "@/lib/app-settings";

export function GoogleSearchAction({
  href,
  subject,
  variant,
}: {
  href: string;
  subject: string;
  variant: "compact" | "labeled";
}) {
  const { t } = useCopy();
  const accessibleName = t("searchSubjectWithGoogle", { subject });
  const anchor = (
    <a href={href} target="_blank" rel="noreferrer" aria-label={accessibleName}>
      {variant === "compact" ? (
        <Search aria-hidden />
      ) : (
        <>
          <GoogleIcon aria-hidden data-icon="inline-start" />
          {t("searchWithGoogle")}
          <ExternalLink aria-hidden data-icon="inline-end" />
        </>
      )}
    </a>
  );

  if (variant === "labeled") {
    return <Button variant="outline" size="sm" render={anchor} />;
  }

  return (
    <Tooltip>
      <TooltipTrigger
        render={<Button variant="outline" size="icon-sm" render={anchor} />}
      />
      <TooltipContent>{accessibleName}</TooltipContent>
    </Tooltip>
  );
}
