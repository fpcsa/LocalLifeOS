import { HardDrive, WifiOff } from "lucide-react";

import { Panel } from "@/components/ui/panel";

export default function OfflinePage() {
  return (
    <div className="mx-auto max-w-2xl py-8">
      <Panel className="p-6 sm:p-8">
        <div className="flex items-start gap-4">
          <div className="rounded-md bg-muted p-3">
            <WifiOff aria-hidden="true" className="h-6 w-6" />
          </div>
          <div className="space-y-3">
            <h1 className="text-xl font-semibold">Application shell available offline</h1>
            <p className="text-sm leading-6 text-muted-foreground">
              LocalLife OS does not need the public Internet. Reconnect the browser to the local
              service on this device to read or change workspace data.
            </p>
            <p className="flex items-center gap-2 text-sm font-medium">
              <HardDrive aria-hidden="true" className="h-4 w-4" />
              Personal API responses are never stored in the service-worker cache.
            </p>
          </div>
        </div>
      </Panel>
    </div>
  );
}
