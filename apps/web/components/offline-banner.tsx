"use client";

import { useQuery } from "@tanstack/react-query";
import { WifiOff } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

import { queryKeys } from "@/lib/api/query-keys";
import { getHealth } from "@/lib/api/system";

const OFFLINE_SESSION_KEY = "locallife.browser-offline";

function subscribeToBrowserConnection(callback: () => void): () => void {
  const update = () => {
    if (navigator.onLine) window.sessionStorage.removeItem(OFFLINE_SESSION_KEY);
    else window.sessionStorage.setItem(OFFLINE_SESSION_KEY, "true");
    callback();
  };
  window.addEventListener("online", update);
  window.addEventListener("offline", update);
  return () => {
    window.removeEventListener("online", update);
    window.removeEventListener("offline", update);
  };
}

function browserConnectionSnapshot(): boolean {
  return window.sessionStorage.getItem(OFFLINE_SESSION_KEY) === "true" || !navigator.onLine;
}

export function OfflineBanner() {
  const browserOffline = useSyncExternalStore(subscribeToBrowserConnection, browserConnectionSnapshot, () => false);
  const healthQuery = useQuery({
    queryKey: queryKeys.system.health,
    queryFn: ({ signal }) => getHealth(signal),
    retry: false,
  });
  useEffect(() => {
    if (!healthQuery.isSuccess || !navigator.onLine) return;
    window.sessionStorage.removeItem(OFFLINE_SESSION_KEY);
  }, [healthQuery.isSuccess]);
  const recovered = healthQuery.isSuccess && typeof navigator !== "undefined" && navigator.onLine;
  if ((!browserOffline || recovered) && !healthQuery.isError) return null;
  return (
    <div className="flex min-h-10 items-center justify-center gap-2 bg-warning px-4 py-2 text-sm font-medium text-warning-foreground" role="status">
      <WifiOff aria-hidden="true" className="h-4 w-4" />
      Local connection is offline. The cached shell remains available; workspace changes need the local service.
    </div>
  );
}
