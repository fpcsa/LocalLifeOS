"use client";

import { useQuery } from "@tanstack/react-query";
import { RotateCcw } from "lucide-react";

import { getHealth } from "@/lib/api/system";
import { queryKeys } from "@/lib/api/query-keys";

const STATUS_CLASS =
  "inline-flex min-h-10 items-center gap-2 rounded-md border px-3 text-xs font-medium";

export function SystemStatus() {
  const healthQuery = useQuery({
    queryKey: queryKeys.system.health,
    queryFn: ({ signal }) => getHealth(signal),
  });

  if (healthQuery.isPending) {
    return (
      <div
        aria-live="polite"
        className={`${STATUS_CLASS} border-border bg-muted text-muted-foreground`}
        role="status"
      >
        <span
          aria-hidden="true"
          className="h-2 w-2 animate-pulse rounded-full bg-muted-foreground"
        />
        Checking local service
      </div>
    );
  }

  if (healthQuery.isError) {
    return (
      <button
        className={`${STATUS_CLASS} border-destructive/40 bg-background text-destructive transition-colors hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`}
        onClick={() => void healthQuery.refetch()}
        type="button"
      >
        <RotateCcw aria-hidden="true" className="h-4 w-4" />
        Local service offline — retry
      </button>
    );
  }

  return (
    <div
      aria-live="polite"
      className={`${STATUS_CLASS} border-success/30 bg-success/10 text-success`}
      role="status"
      title={`LocalLife OS API ${healthQuery.data.version}`}
    >
      <span aria-hidden="true" className="h-2 w-2 rounded-full bg-success" />
      Local service online
    </div>
  );
}
