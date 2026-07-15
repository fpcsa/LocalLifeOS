"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";

import { Button } from "./button";

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      aria-describedby={description ? descriptionId : undefined}
      aria-labelledby={titleId}
      className={`max-h-[90vh] w-[calc(100%-2rem)] overflow-hidden rounded-lg border border-border bg-card p-0 text-card-foreground shadow-xl backdrop:bg-foreground/25 ${wide ? "max-w-3xl" : "max-w-lg"}`}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      onClose={onClose}
      ref={ref}
    >
      <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
        <div className="space-y-1">
          <h2 className="text-base font-semibold" id={titleId}>
            {title}
          </h2>
          {description ? (
            <p className="text-sm leading-5 text-muted-foreground" id={descriptionId}>
              {description}
            </p>
          ) : null}
        </div>
        <Button aria-label={`Close ${title}`} onClick={onClose} size="icon" type="button" variant="ghost">
          <X aria-hidden="true" className="h-5 w-5" />
        </Button>
      </div>
      <div className="max-h-[calc(90vh-5rem)] overflow-y-auto p-5">{children}</div>
    </dialog>
  );
}
