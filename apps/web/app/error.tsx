"use client";

import { ErrorState } from "@/components/ui/states";

export default function ErrorBoundary({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ErrorState description="This route failed to render. No local data was changed." retry={reset} />;
}
