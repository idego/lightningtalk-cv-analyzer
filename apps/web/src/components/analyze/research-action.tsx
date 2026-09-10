"use client";

import { type ReactNode, useState } from "react";
import { Play } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export function ResearchAction({
  busy,
  disabled,
  onClick,
  label,
  busyLabel,
  busyAriaLabel,
  disabledReason,
  confirmHint,
  confirmLabel,
}: {
  busy: boolean;
  disabled: boolean;
  onClick: () => void;
  label: string;
  busyLabel: string;
  busyAriaLabel: string;
  disabledReason?: string;
  /** When set, the first click only shows this hint; the second click runs. */
  confirmHint?: string;
  confirmLabel?: string;
}) {
  const [armed, setArmed] = useState(false);
  const needsConfirmation = Boolean(confirmHint) && !disabled && !busy;
  const button: ReactNode = (
    <Button
      type="button"
      variant="outline"
      disabled={disabled}
      aria-describedby={armed ? "research-action-hint" : undefined}
      onBlur={() => setArmed(false)}
      onKeyDown={(event) => { if (event.key === "Escape") setArmed(false); }}
      onClick={() => {
        if (needsConfirmation && !armed) { setArmed(true); return; }
        setArmed(false);
        onClick();
      }}
    >
      {busy ? (
        <span className="flex items-center gap-2">
          <ThinkingOrb state="working" size={20} theme="auto" aria-label={busyAriaLabel} />
          {busyLabel}
        </span>
      ) : <><Play aria-hidden data-icon="inline-start" />{armed && confirmLabel ? confirmLabel : label}</>}
    </Button>
  );

  if (needsConfirmation) {
    return (
      <div className="relative shrink-0">
        {button}
        {armed ? <span id="research-action-hint" role="status" className="absolute right-0 top-full z-20 mt-2 max-w-64 rounded-md bg-foreground px-2 py-1 text-xs text-background shadow-md">{confirmHint}</span> : null}
      </div>
    );
  }

  if (!disabledReason) return button;

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            tabIndex={0}
            aria-label={disabledReason}
            className="inline-flex"
          >
            {button}
          </span>
        }
      />
      <TooltipContent side="top">{disabledReason}</TooltipContent>
    </Tooltip>
  );
}
