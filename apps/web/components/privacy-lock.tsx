"use client";

import { useQuery } from "@tanstack/react-query";
import { LockKeyhole } from "lucide-react";
import { useEffect, useRef, type KeyboardEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { getPreferences } from "@/lib/api/connected";
import { queryKeys } from "@/lib/api/query-keys";
import { useUiStore } from "@/stores/ui-store";

const LAST_ACTIVITY_KEY = "locallife.last-activity";
const ACTIVITY_EVENTS = ["keydown", "pointerdown", "touchstart", "focus"] as const;

export function PrivacyLock({ children }: { children: ReactNode }) {
  const preferences = useQuery({
    queryKey: queryKeys.system.preferences,
    queryFn: getPreferences,
  });
  const locked = useUiStore((state) => state.privacyLocked);
  const lockPrivacy = useUiStore((state) => state.lockPrivacy);
  const unlockPrivacy = useUiStore((state) => state.unlockPrivacy);
  const unlockRef = useRef<HTMLButtonElement>(null);
  const lockedRef = useRef(locked);

  useEffect(() => {
    lockedRef.current = locked;
  }, [locked]);

  useEffect(() => {
    if (!preferences.data) return;
    const timeoutMilliseconds = preferences.data.session_timeout_minutes * 60_000;
    const stored = Number(window.localStorage.getItem(LAST_ACTIVITY_KEY) ?? Date.now());
    let lastActivity = Number.isFinite(stored) ? stored : Date.now();
    if (Date.now() - lastActivity >= timeoutMilliseconds) lockPrivacy();

    const recordActivity = () => {
      if (lockedRef.current) return;
      const now = Date.now();
      if (now - lastActivity < 5_000) return;
      lastActivity = now;
      window.localStorage.setItem(LAST_ACTIVITY_KEY, String(now));
    };
    for (const eventName of ACTIVITY_EVENTS) {
      window.addEventListener(eventName, recordActivity, { passive: true });
    }
    const timer = window.setInterval(() => {
      if (!lockedRef.current && Date.now() - lastActivity >= timeoutMilliseconds) lockPrivacy();
    }, 10_000);
    return () => {
      window.clearInterval(timer);
      for (const eventName of ACTIVITY_EVENTS) window.removeEventListener(eventName, recordActivity);
    };
  }, [lockPrivacy, preferences.data]);

  useEffect(() => {
    if (locked) unlockRef.current?.focus();
  }, [locked]);

  function unlock() {
    window.localStorage.setItem(LAST_ACTIVITY_KEY, String(Date.now()));
    unlockPrivacy();
  }

  function trapFocus(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Tab") {
      event.preventDefault();
      unlockRef.current?.focus();
    }
  }

  const active = locked;
  return (
    <>
      <div aria-hidden={active || undefined} inert={active || undefined}>
        {children}
      </div>
      {active ? (
        <div
          aria-describedby="privacy-lock-description"
          aria-labelledby="privacy-lock-title"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-background px-4"
          onKeyDown={trapFocus}
          role="dialog"
        >
          <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 text-center shadow-lg">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <LockKeyhole aria-hidden="true" className="h-6 w-6" />
            </div>
            <h1 className="text-lg font-semibold" id="privacy-lock-title">
              Privacy screen locked
            </h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground" id="privacy-lock-description">
              This hides the interface after inactivity. It is not user authentication and does
              not protect the local API from other software running as you.
            </p>
            <Button className="mt-5 w-full" onClick={unlock} ref={unlockRef} type="button">
              Unlock on this device
            </Button>
          </div>
        </div>
      ) : null}
    </>
  );
}
