"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

type Confirmation = { description: string; title?: string; action?: string };

export function useConfirmation() {
  const [request, setRequest] = useState<Confirmation | null>(null);
  const resolveRef = useRef<((confirmed: boolean) => void) | null>(null);
  const finish = useCallback((confirmed: boolean) => {
    const resolve = resolveRef.current;
    resolveRef.current = null;
    setRequest(null);
    resolve?.(confirmed);
  }, []);
  const confirm = useCallback((description: string, options: Omit<Confirmation, "description"> = {}) => {
    resolveRef.current?.(false);
    setRequest({ description, ...options });
    return new Promise<boolean>((resolve) => { resolveRef.current = resolve; });
  }, []);
  useEffect(() => () => { resolveRef.current?.(false); }, []);
  const confirmationDialog = <Dialog open={request !== null} onOpenChange={(open) => { if (!open) finish(false); }}>
    <DialogContent className="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>{request?.title ?? "Confirm change"}</DialogTitle>
        <DialogDescription>{request?.description}</DialogDescription>
      </DialogHeader>
      <DialogFooter>
        <Button variant="outline" onClick={() => finish(false)}>Cancel</Button>
        <Button variant="destructive" onClick={() => finish(true)}>{request?.action ?? "Confirm"}</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>;
  return { confirm, confirmationDialog };
}
