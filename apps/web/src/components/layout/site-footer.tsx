"use client";

import { useCopy } from "@/lib/app-settings";

export function SiteFooter() {
  const { t } = useCopy();

  return (
    <footer className="mt-auto shrink-0 px-4 py-3 text-center text-xs text-muted-foreground md:px-6">
      <p>
        © {new Date().getFullYear()} {" "}
        <a
          href="https://idego.io"
          className="font-medium text-foreground underline-offset-4 hover:underline"
          target="_blank"
          rel="noopener noreferrer"
        >
          Idego
        </a>
        . {t("allRightsReserved")}
      </p>
    </footer>
  );
}
