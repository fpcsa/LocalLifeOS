"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { getPreferences } from "@/lib/api/connected";
import { queryKeys } from "@/lib/api/query-keys";

export function ThemeSync() {
  const preferences = useQuery({ queryKey: queryKeys.system.preferences, queryFn: getPreferences });
  useEffect(() => {
    if (!preferences.data) return;
    if (preferences.data.theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = preferences.data.theme;
  }, [preferences.data]);
  return null;
}
