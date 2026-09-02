"use client";

import { useState, type MouseEvent, type ReactNode } from "react";
import { Collapsible } from "@base-ui/react/collapsible";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppSettings } from "@/lib/app-settings";

type HoverDisclosureProps = {
  title: ReactNode;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
  triggerClassName?: string;
  headerClassName?: string;
  actionClassName?: string;
  panelClassName?: string;
  contentClassName?: string;
  defaultOpen?: boolean;
  allowHover?: boolean;
  collapsible?: boolean;
  feedbackSnapshotLabel?: string;
};

export function HoverDisclosure({
  title,
  children,
  action,
  className,
  triggerClassName,
  headerClassName,
  actionClassName,
  panelClassName,
  contentClassName,
  defaultOpen = false,
  allowHover = false,
  collapsible = true,
  feedbackSnapshotLabel,
}: HoverDisclosureProps) {
  const { previewFindingsOnHover, expandSectionsByDefault } = useAppSettings();
  const initialOpen = defaultOpen || expandSectionsByDefault;
  const [open, setOpen] = useState(initialOpen);
  const [pinned, setPinned] = useState(initialOpen);

  function setHoverOpen(nextOpen: boolean) {
    if (!allowHover || !previewFindingsOnHover || pinned || typeof window === "undefined") return;
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    setOpen(nextOpen);
  }

  function toggleFromCard(event: MouseEvent<HTMLElement>) {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (target.closest("[data-disclosure-trigger], [data-disclosure-panel], a, button, input, select, textarea")) return;

    if (open && !pinned && allowHover) {
      setPinned(true);
      return;
    }
    const nextOpen = !open;
    setPinned(nextOpen);
    setOpen(nextOpen);
  }

  function changeOpen(nextOpen: boolean) {
    if (!nextOpen && open && !pinned && allowHover && previewFindingsOnHover) {
      setPinned(true);
      setOpen(true);
      return;
    }
    setOpen(nextOpen);
  }

  if (!collapsible) {
    return (
      <div className={className} data-feedback-snapshot={feedbackSnapshotLabel}>
        <div className={cn("flex items-center gap-3", headerClassName)}>
          <div className={cn("flex min-w-0 flex-1 items-center gap-3 text-left", triggerClassName)}>
            <span className="min-w-0 flex-1">{title}</span>
          </div>
          {action ? <div className={cn("shrink-0", actionClassName)}>{action}</div> : null}
        </div>
      </div>
    );
  }

  return (
    <Collapsible.Root
      open={open}
      onOpenChange={changeOpen}
      onClick={toggleFromCard}
      onPointerEnter={() => setHoverOpen(true)}
      onPointerLeave={() => setHoverOpen(false)}
      className={cn("group/disclosure", !open && "cursor-pointer", className)}
      data-feedback-snapshot={feedbackSnapshotLabel}
    >
      <div className={cn("flex items-center gap-3", headerClassName)}>
        <Collapsible.Trigger
          data-disclosure-trigger
          onClick={(event) => {
            if (open && !pinned && allowHover && previewFindingsOnHover) {
              event.preventDefault();
              setPinned(true);
              setOpen(true);
              return;
            }
            setPinned(!open);
          }}
          className={cn(
            "flex min-w-0 flex-1 cursor-pointer items-center justify-between gap-3 rounded-sm text-left outline-none focus-visible:ring-2 focus-visible:ring-ring",
            triggerClassName,
          )}
        >
          <span className="min-w-0 flex-1">{title}</span>
          <ChevronDown
            aria-hidden="true"
            className={cn(
              "size-4 shrink-0 transition-transform duration-[180ms] ease-[var(--motion-ease-out)] motion-reduce:transition-none",
              open && "rotate-180",
            )}
          />
        </Collapsible.Trigger>
        {action ? <div className={cn("shrink-0", actionClassName)}>{action}</div> : null}
      </div>
      <Collapsible.Panel
        data-disclosure-panel
        className={cn(
          "h-[var(--collapsible-panel-height)] overflow-hidden opacity-100 transition-[height,opacity] duration-[180ms] ease-[var(--motion-ease-out)] data-open:overflow-visible data-ending-style:h-0 data-ending-style:overflow-hidden data-ending-style:opacity-0 data-starting-style:h-0 data-starting-style:overflow-hidden data-starting-style:opacity-0 motion-reduce:transition-none",
          panelClassName,
        )}
      >
        <div className={contentClassName}>{children}</div>
      </Collapsible.Panel>
    </Collapsible.Root>
  );
}
