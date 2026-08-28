"use client";

import { LogOut } from "lucide-react";
import { authClient } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";
import { useCopy } from "@/lib/app-settings";

export function SignOutButton() {
  const { t } = useCopy();

  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-8 gap-1 px-2 text-xs"
      onClick={() =>
        authClient.signOut({
          fetchOptions: {
            onSuccess: () => {
              window.location.href = "/sign-in";
            },
          },
        })
      }
      aria-label={t("signOut")}
      title={t("signOut")}
    >
      <LogOut className="size-3.5" />
      {t("signOut")}
    </Button>
  );
}
