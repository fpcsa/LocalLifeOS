import { AlertCircle, Inbox, RotateCw } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "./button";

export function SkeletonList({ rows = 4 }: { rows?: number }) {
  return (
    <div aria-label="Loading" className="space-y-3" role="status">
      {Array.from({ length: rows }, (_, index) => (
        <div className="h-16 animate-pulse rounded-lg bg-muted" key={index} />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center gap-3 px-6 py-10 text-center">
      <Inbox aria-hidden="true" className="h-8 w-8 text-muted-foreground" />
      <div className="space-y-1">
        <p className="text-sm font-semibold">{title}</p>
        <p className="max-w-md text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      {action}
    </div>
  );
}

export function ErrorState({
  title = "Couldn't load this view",
  description = "The local API may be restarting. Your data has not been changed.",
  retry,
}: {
  title?: string;
  description?: string;
  retry?: () => void;
}) {
  return (
    <div className="flex min-h-40 flex-col items-start justify-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-5" role="alert">
      <div className="flex items-center gap-2 text-destructive">
        <AlertCircle aria-hidden="true" className="h-5 w-5" />
        <p className="text-sm font-semibold">{title}</p>
      </div>
      <p className="max-w-prose text-sm leading-6 text-muted-foreground">{description}</p>
      {retry ? (
        <Button onClick={retry} type="button" variant="secondary">
          <RotateCw aria-hidden="true" className="h-4 w-4" />
          Try again
        </Button>
      ) : null}
    </div>
  );
}
