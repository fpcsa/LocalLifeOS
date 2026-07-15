"use client";

import { CheckCircle2, CircleAlert, X } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { useUiStore } from "@/stores/ui-store";

function ToastTimer({ id }: { id: string }) {
  const dismiss = useUiStore((state) => state.dismissToast);
  useEffect(() => {
    const timer = window.setTimeout(() => dismiss(id), 5_000);
    return () => window.clearTimeout(timer);
  }, [dismiss, id]);
  return null;
}

export function ToastViewport() {
  const toasts = useUiStore((state) => state.toasts);
  const dismiss = useUiStore((state) => state.dismissToast);
  return (
    <div aria-atomic="true" aria-live="polite" className="fixed bottom-4 right-4 z-50 flex w-[min(24rem,calc(100%-2rem))] flex-col gap-2">
      {toasts.map((toast) => (
        <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-4 shadow-lg" key={toast.id} role="status">
          <ToastTimer id={toast.id} />
          {toast.tone === "error" ? (
            <CircleAlert aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
          ) : (
            <CheckCircle2 aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-success" />
          )}
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold">{toast.title}</p>
            {toast.description ? <p className="mt-1 text-xs leading-5 text-muted-foreground">{toast.description}</p> : null}
          </div>
          <Button aria-label="Dismiss notification" onClick={() => dismiss(toast.id)} size="icon" type="button" variant="ghost">
            <X aria-hidden="true" className="h-4 w-4" />
          </Button>
        </div>
      ))}
    </div>
  );
}
