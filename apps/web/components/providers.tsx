"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { CommandPalette } from "@/components/command-palette";
import { OfflineBanner } from "@/components/offline-banner";
import { PrivacyLock } from "@/components/privacy-lock";
import { QuickCreate } from "@/components/quick-create";
import { ServiceWorkerRegistration } from "@/components/service-worker-registration";
import { ToastViewport } from "@/components/toast-viewport";
import { ThemeSync } from "@/components/theme-sync";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            retry: 1,
            staleTime: 30_000,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeSync />
      <ServiceWorkerRegistration />
      <OfflineBanner />
      <PrivacyLock>
        {children}
        <CommandPalette />
        <QuickCreate />
        <ToastViewport />
      </PrivacyLock>
    </QueryClientProvider>
  );
}
