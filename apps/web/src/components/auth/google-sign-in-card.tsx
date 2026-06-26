"use client";

import { useState } from "react";
import { authClient } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  AuthPageShell,
  Login07GoogleIcon,
} from "@/components/auth/login-07-shared";

export function GoogleSignInCard({
  showGoogle,
  callbackURL,
}: {
  showGoogle: boolean;
  callbackURL: string;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function signInWithGoogle() {
    setPending(true);
    setError(null);

    try {
      const origin =
        typeof window !== "undefined" ? window.location.origin : "";
      await authClient.signIn.social({
        provider: "google",
        callbackURL: `${origin}${callbackURL.startsWith("/") ? callbackURL : `/${callbackURL}`}`,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in.");
      setPending(false);
    }
  }

  return (
    <AuthPageShell
      title="Welcome back"
      description="Sign in to CV Analyzer with your Idego Google account."
    >
      <div className="space-y-5">
        <Button
          type="button"
          variant="outline"
          className="w-full justify-center gap-2"
          onClick={() => void signInWithGoogle()}
          disabled={pending || !showGoogle}
        >
          <Login07GoogleIcon className="h-4 w-4" />
          {pending ? "Signing in..." : "Sign in with Google"}
        </Button>
        <div className="flex items-center gap-2">
          <Separator className="flex-1" />
          <span className="text-muted-foreground text-sm">Google SSO only</span>
          <Separator className="flex-1" />
        </div>
        {!showGoogle ? (
          <p className="text-sm text-destructive">
            Google OAuth is not configured.
          </p>
        ) : null}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </div>
    </AuthPageShell>
  );
}
