"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, HardDrive, LockKeyhole, WifiOff } from "lucide-react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form-controls";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { ErrorState, SkeletonList } from "@/components/ui/states";
import { getPreferences, updatePreferences } from "@/lib/api/connected";
import { queryKeys } from "@/lib/api/query-keys";
import { getSystemInfo } from "@/lib/api/system";
import type { Preferences } from "@/lib/api/types";
import { useUiStore } from "@/stores/ui-store";

interface Values { locale: string; timezone: string; currency: string; weekStartsOn: string; theme: Preferences["theme"] }

export function SettingsWorkspace() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const preferences = useQuery({ queryKey: queryKeys.system.preferences, queryFn: getPreferences });
  const system = useQuery({ queryKey: queryKeys.system.info, queryFn: ({ signal }) => getSystemInfo(signal) });
  const { register, handleSubmit, reset, formState: { errors, isDirty } } = useForm<Values>({ defaultValues: { locale: "en", timezone: "UTC", currency: "EUR", weekStartsOn: "1", theme: "system" } });
  useEffect(() => { if (preferences.data) reset({ locale: preferences.data.locale, timezone: preferences.data.timezone, currency: preferences.data.currency_code, weekStartsOn: String(preferences.data.week_starts_on), theme: preferences.data.theme }); }, [preferences.data, reset]);
  const save = useMutation({ mutationFn: (values: Values) => updatePreferences({ revision: preferences.data!.revision, locale: values.locale, timezone: values.timezone, currency_code: values.currency.toUpperCase(), week_starts_on: Number(values.weekStartsOn), theme: values.theme }), onSuccess: (saved) => { queryClient.setQueryData(queryKeys.system.preferences, saved); reset({ locale: saved.locale, timezone: saved.timezone, currency: saved.currency_code, weekStartsOn: String(saved.week_starts_on), theme: saved.theme }); pushToast({ title: "Preferences saved", tone: "success" }); }, onError: (error) => pushToast({ title: "Couldn't save preferences", description: error instanceof Error ? error.message : "Reload and try again.", tone: "error" }) });
  if (preferences.isLoading || system.isLoading) return <SkeletonList rows={7} />;
  if (preferences.isError || system.isError) return <ErrorState retry={() => { void preferences.refetch(); void system.refetch(); }} />;
  return <div className="space-y-6"><PageHeader title="Settings" description="Device-local preferences for time, money, week layout, and appearance." /><div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]"><Panel><PanelHeader title="Regional preferences" description="Timezone controls date boundaries; currency controls default finance entry formatting." /><form className="space-y-5 p-5" onSubmit={handleSubmit((values) => save.mutate(values))}><div className="grid gap-4 md:grid-cols-2"><Field error={errors.locale?.message} id="settings-locale" label="Locale" required><Input id="settings-locale" placeholder="en-GB" {...register("locale", { required: "Enter a locale." })} /></Field><Field error={errors.timezone?.message} id="settings-timezone" label="Timezone" hint="IANA name, for example Europe/Rome" required><Input id="settings-timezone" placeholder="Europe/Rome" {...register("timezone", { required: "Enter a timezone." })} /></Field></div><div className="grid gap-4 md:grid-cols-3"><Field id="settings-currency" label="Default currency"><Input id="settings-currency" maxLength={3} {...register("currency", { required: true })} /></Field><Field id="settings-week-start" label="Week starts on"><Select id="settings-week-start" {...register("weekStartsOn")}><option value="0">Sunday</option><option value="1">Monday</option><option value="2">Tuesday</option><option value="3">Wednesday</option><option value="4">Thursday</option><option value="5">Friday</option><option value="6">Saturday</option></Select></Field><Field id="settings-theme" label="Appearance"><Select id="settings-theme" {...register("theme")}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></Select></Field></div><div className="flex items-center justify-between gap-4 border-t border-border pt-5"><p className="text-xs text-muted-foreground">{isDirty ? "Unsaved changes" : "Preferences are up to date"}</p><Button disabled={!isDirty} loading={save.isPending} type="submit">Save preferences</Button></div></form></Panel><div className="space-y-5"><Panel><PanelHeader title="Local system" /><dl className="space-y-3 p-4 text-sm"><div className="flex justify-between gap-3"><dt className="text-muted-foreground">Application</dt><dd className="font-medium">{system.data?.application}</dd></div><div className="flex justify-between gap-3"><dt className="text-muted-foreground">Version</dt><dd>{system.data?.version}</dd></div><div className="flex justify-between gap-3"><dt className="text-muted-foreground">Storage</dt><dd><Badge>{system.data?.storage}</Badge></dd></div><div className="flex justify-between gap-3"><dt className="text-muted-foreground">Environment</dt><dd>{system.data?.environment}</dd></div></dl></Panel><Panel><PanelHeader title="Privacy guarantees" /><ul className="space-y-4 p-4 text-sm"><li className="flex gap-3"><HardDrive aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" /><span>SQLite and attachments remain on this device.</span></li><li className="flex gap-3"><WifiOff aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" /><span>External runtime requests are disabled.</span></li><li className="flex gap-3"><Database aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" /><span>Telemetry is disabled.</span></li><li className="flex gap-3"><LockKeyhole aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" /><span>Encryption is not claimed; use device-level protection.</span></li></ul></Panel></div></div></div>;
}
