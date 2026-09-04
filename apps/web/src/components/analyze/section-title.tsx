import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Icon + label used by collapsible module headers. The icon wrapper is a flex
 * item (never an inline box) so the SVG cannot ride the text baseline, and it is
 * nudged up 1px to sit on the optical (cap-height) center of the label.
 */
export function SectionTitle({ icon, children, className }: { icon: ReactNode; children: ReactNode; className?: string }) {
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <span className="flex shrink-0 -translate-y-px items-center justify-center text-muted-foreground [&>svg]:block" aria-hidden>
        {icon}
      </span>
      <span className="min-w-0">{children}</span>
    </span>
  );
}
