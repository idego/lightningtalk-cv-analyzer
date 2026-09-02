"use client";

import type { ReactNode } from "react";
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
}: {
  busy: boolean;
  disabled: boolean;
  onClick: () => void;
  label: string;
  busyLabel: string;
  busyAriaLabel: string;
  disabledReason?: string;
}) {
  const button: ReactNode = (
    <Button type="button" variant="outline" onClick={onClick} disabled={disabled}>
      {busy ? (
        <span className="flex items-center gap-2">
          <ThinkingOrb state="working" size={20} theme="auto" aria-label={busyAriaLabel} />
          {busyLabel}
        </span>
      ) : <><Play aria-hidden data-icon="inline-start" />{label}</>}
    </Button>
  );

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
