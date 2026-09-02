"use client";

import { ExternalLink } from "lucide-react";
import { GoogleIcon } from "@/components/ui/google-icon";
import { Button } from "@/components/ui/button";
import { useCopy } from "@/lib/app-settings";

export function GoogleSearchAction({
  href,
}: {
  href: string;
}) {
  const { t } = useCopy();
  return (
    <Button variant="outline" size="sm" nativeButton={false} render={
      <a href={href} target="_blank" rel="noreferrer">
        <GoogleIcon aria-hidden data-icon="inline-start" />
        {t("searchWithGoogle")}
        <ExternalLink aria-hidden data-icon="inline-end" />
      </a>
    } />
  );
}
