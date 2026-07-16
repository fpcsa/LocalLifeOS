"use client";

import { useQuery } from "@tanstack/react-query";
import { WifiOff } from "lucide-react";
import { useEffect, useState } from "react";

import { queryKeys } from "@/lib/api/query-keys";
import { getHealth } from "@/lib/api/system";

export function OfflineBanner() {
  const [browserOffline, setBrowserOffline] = useState(false);
  const healthQuery = useQuery({
    queryKey: queryKeys.system.health,
    queryFn: ({ signal }) => getHealth(signal),
    retry: false,
  });
  useEffect(() => {
    const update = () => setBrowserOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  if (!browserOffline && !healthQuery.isError) return null;
  return (
    <div className="flex min-h-10 items-center justify-center gap-2 bg-warning px-4 py-2 text-sm font-medium text-warning-foreground" role="status">
      <WifiOff aria-hidden="true" className="h-4 w-4" />
      Local connection is offline. The cached shell remains available; workspace changes need the local service.
    </div>
  );
}
