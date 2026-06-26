"use client";

import { LogOut } from "lucide-react";
import { authClient } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";

export function SignOutButton() {
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
      aria-label="Sign out"
      title="Sign out"
    >
      <LogOut className="size-3.5" />
      Sign out
    </Button>
  );
}
