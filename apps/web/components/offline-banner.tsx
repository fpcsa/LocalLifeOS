"use client";

import { WifiOff } from "lucide-react";
import { useEffect, useState } from "react";

export function OfflineBanner() {
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  if (!offline) return null;
  return (
    <div className="flex min-h-10 items-center justify-center gap-2 bg-warning px-4 py-2 text-sm font-medium text-warning-foreground" role="status">
      <WifiOff aria-hidden="true" className="h-4 w-4" />
      Offline. Read-only cached views may remain visible; changes are paused.
    </div>
  );
}
