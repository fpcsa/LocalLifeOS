"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArchiveRestore,
  Database,
  Eye,
  EyeOff,
  HardDrive,
  LockKeyhole,
  ShieldCheck,
  Trash2,
  WifiOff,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form-controls";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { ErrorState, SkeletonList } from "@/components/ui/states";
import { getPreferences, updatePreferences } from "@/lib/api/connected";
import {
  createLocalBackup,
  deleteAllLocalData,
  getPrivacyStatus,
} from "@/lib/api/privacy";
import { queryKeys } from "@/lib/api/query-keys";
import { getSystemInfo } from "@/lib/api/system";
import type { Preferences } from "@/lib/api/types";
import { useUiStore } from "@/stores/ui-store";

interface PreferenceValues {
  locale: string;
  timezone: string;
  currency: string;
  weekStartsOn: string;
  theme: Preferences["theme"];
  sessionTimeoutMinutes: string;
}

interface BackupValues {
  label: string;
  password: string;
  passwordConfirmation: string;
}

const defaultPreferences: PreferenceValues = {
  locale: "en",
  timezone: "UTC",
  currency: "EUR",
  weekStartsOn: "1",
  theme: "system",
  sessionTimeoutMinutes: "30",
};

function formatBytes(value: number): string {
  const units = ["B", "KB", "MB", "GB"];
  let amount = value;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export function SettingsWorkspace() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const lockPrivacy = useUiStore((state) => state.lockPrivacy);
  const preferences = useQuery({
    queryKey: queryKeys.system.preferences,
    queryFn: getPreferences,
  });
  const system = useQuery({
    queryKey: queryKeys.system.info,
    queryFn: ({ signal }) => getSystemInfo(signal),
  });
  const privacy = useQuery({
    queryKey: queryKeys.system.privacy,
    queryFn: getPrivacyStatus,
  });
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<PreferenceValues>({ defaultValues: defaultPreferences });
  const backupForm = useForm<BackupValues>({
    defaultValues: { label: "", password: "", passwordConfirmation: "" },
  });
  const [showPassword, setShowPassword] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [includeBackups, setIncludeBackups] = useState(false);

  useEffect(() => {
    if (!preferences.data) return;
    reset({
      locale: preferences.data.locale,
      timezone: preferences.data.timezone,
      currency: preferences.data.currency_code,
      weekStartsOn: String(preferences.data.week_starts_on),
      theme: preferences.data.theme,
      sessionTimeoutMinutes: String(preferences.data.session_timeout_minutes),
    });
  }, [preferences.data, reset]);

  const save = useMutation({
    mutationFn: (values: PreferenceValues) =>
      updatePreferences({
        revision: preferences.data!.revision,
        locale: values.locale,
        timezone: values.timezone,
        currency_code: values.currency.toUpperCase(),
        week_starts_on: Number(values.weekStartsOn),
        theme: values.theme,
        session_timeout_minutes: Number(values.sessionTimeoutMinutes),
      }),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.system.preferences, saved);
      reset({
        locale: saved.locale,
        timezone: saved.timezone,
        currency: saved.currency_code,
        weekStartsOn: String(saved.week_starts_on),
        theme: saved.theme,
        sessionTimeoutMinutes: String(saved.session_timeout_minutes),
      });
      pushToast({ title: "Preferences saved", tone: "success" });
    },
    onError: (error) =>
      pushToast({
        title: "Couldn't save preferences",
        description: error instanceof Error ? error.message : "Reload and try again.",
        tone: "error",
      }),
  });

  const createBackup = useMutation({
    mutationFn: (values: BackupValues) =>
      createLocalBackup({
        ...(values.label.trim() ? { label: values.label.trim() } : {}),
        ...(values.password ? { password: values.password } : {}),
      }),
    onSuccess: async (result) => {
      backupForm.reset();
      await queryClient.invalidateQueries({ queryKey: queryKeys.system.privacy });
      pushToast({
        title: "Backup created and verified",
        description: `${result.backup.filename} · ${formatBytes(result.backup.size_bytes)}`,
        tone: "success",
      });
    },
    onError: (error) =>
      pushToast({
        title: "Backup failed",
        description: error instanceof Error ? error.message : "Review the local backup settings.",
        tone: "error",
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: () =>
      deleteAllLocalData({
        confirmation: "DELETE ALL LOCAL DATA",
        include_backups: includeBackups,
      }),
    onSuccess: (result) => {
      setDeleteOpen(false);
      setDeleteConfirmation("");
      queryClient.clear();
      pushToast({
        title: "Local workspace cleared",
        description: `${result.deleted_database_records} database records and ${result.deleted_attachment_files + result.deleted_import_files} local files removed.`,
        tone: "success",
      });
      window.setTimeout(() => window.location.assign("/"), 800);
    },
    onError: (error) =>
      pushToast({
        title: "Delete failed safely",
        description: error instanceof Error ? error.message : "No deletion was confirmed.",
        tone: "error",
      }),
  });

  if (preferences.isLoading || system.isLoading || privacy.isLoading) {
    return <SkeletonList rows={9} />;
  }
  if (preferences.isError || system.isError || privacy.isError) {
    return (
      <ErrorState
        retry={() => {
          void preferences.refetch();
          void system.refetch();
          void privacy.refetch();
        }}
      />
    );
  }

  const lastBackup = privacy.data?.last_backup;
  return (
    <div className="space-y-6">
      <PageHeader
        description="Device-local preferences, privacy boundaries, backup status, and data controls."
        title="Settings"
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-5">
          <Panel>
            <PanelHeader
              description="Timezone controls date boundaries; currency controls default finance entry formatting."
              title="Regional and session preferences"
            />
            <form
              className="space-y-5 p-5"
              onSubmit={handleSubmit((values) => save.mutate(values))}
            >
              <div className="grid gap-4 md:grid-cols-2">
                <Field error={errors.locale?.message} id="settings-locale" label="Locale" required>
                  <Input
                    autoComplete="off"
                    id="settings-locale"
                    placeholder="en-GB"
                    spellCheck={false}
                    {...register("locale", { required: "Enter a locale." })}
                  />
                </Field>
                <Field
                  error={errors.timezone?.message}
                  hint="IANA name, for example Europe/Rome"
                  id="settings-timezone"
                  label="Timezone"
                  required
                >
                  <Input
                    autoComplete="off"
                    id="settings-timezone"
                    placeholder="Europe/Rome"
                    spellCheck={false}
                    {...register("timezone", { required: "Enter a timezone." })}
                  />
                </Field>
              </div>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Field id="settings-currency" label="Default currency">
                  <Input
                    autoComplete="off"
                    id="settings-currency"
                    maxLength={3}
                    spellCheck={false}
                    {...register("currency", { required: true })}
                  />
                </Field>
                <Field id="settings-week-start" label="Week starts on">
                  <Select id="settings-week-start" {...register("weekStartsOn")}>
                    <option value="0">Sunday</option>
                    <option value="1">Monday</option>
                    <option value="2">Tuesday</option>
                    <option value="3">Wednesday</option>
                    <option value="4">Thursday</option>
                    <option value="5">Friday</option>
                    <option value="6">Saturday</option>
                  </Select>
                </Field>
                <Field id="settings-theme" label="Appearance">
                  <Select id="settings-theme" {...register("theme")}>
                    <option value="system">System</option>
                    <option value="light">Light</option>
                    <option value="dark">Dark</option>
                  </Select>
                </Field>
                <Field
                  hint="Locks only the visible interface after inactivity."
                  id="settings-session-timeout"
                  label="Privacy timeout"
                >
                  <Select id="settings-session-timeout" {...register("sessionTimeoutMinutes")}>
                    <option value="5">5 minutes</option>
                    <option value="15">15 minutes</option>
                    <option value="30">30 minutes</option>
                    <option value="60">1 hour</option>
                    <option value="240">4 hours</option>
                    <option value="1440">24 hours</option>
                  </Select>
                </Field>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-5">
                <p className="text-xs text-muted-foreground">
                  {isDirty ? "Unsaved changes" : "Preferences are up to date"}
                </p>
                <div className="flex gap-2">
                  <Button onClick={lockPrivacy} type="button" variant="secondary">
                    <LockKeyhole aria-hidden="true" className="h-4 w-4" />
                    Lock now
                  </Button>
                  <Button disabled={!isDirty} loading={save.isPending} type="submit">
                    Save preferences
                  </Button>
                </div>
              </div>
            </form>
          </Panel>

          <Panel>
            <PanelHeader
              description="Creates a complete local container with a consistent SQLite snapshot, attachments, preferences, manifest, and checksums."
              title="Backup"
            />
            <form
              className="space-y-5 p-5"
              onSubmit={backupForm.handleSubmit((values) => createBackup.mutate(values))}
            >
              <div className="grid gap-4 md:grid-cols-2">
                <Field
                  error={backupForm.formState.errors.label?.message}
                  hint="Optional letters, numbers, underscores, or hyphens."
                  id="backup-label"
                  label="Backup label"
                >
                  <Input
                    autoComplete="off"
                    id="backup-label"
                    placeholder="before-travel"
                    spellCheck={false}
                    {...backupForm.register("label", {
                      pattern: {
                        value: /^[A-Za-z0-9_-]*$/,
                        message: "Use only letters, numbers, underscores, or hyphens.",
                      },
                    })}
                  />
                </Field>
                <Field
                  error={backupForm.formState.errors.password?.message}
                  hint="Optional. The password is never stored and cannot be recovered."
                  id="backup-password"
                  label="Encryption password"
                >
                  <div className="flex gap-2">
                    <Input
                      autoComplete="new-password"
                      id="backup-password"
                      minLength={8}
                      spellCheck={false}
                      type={showPassword ? "text" : "password"}
                      {...backupForm.register("password", {
                        validate: (value) =>
                          !value || value.length >= 8 || "Use at least 8 characters.",
                      })}
                    />
                    <Button
                      aria-label={showPassword ? "Hide backup password" : "Show backup password"}
                      onClick={() => setShowPassword((value) => !value)}
                      size="icon"
                      type="button"
                      variant="secondary"
                    >
                      {showPassword ? (
                        <EyeOff aria-hidden="true" className="h-4 w-4" />
                      ) : (
                        <Eye aria-hidden="true" className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </Field>
                <Field
                  error={backupForm.formState.errors.passwordConfirmation?.message}
                  id="backup-password-confirmation"
                  label="Confirm encryption password"
                >
                  <Input
                    autoComplete="new-password"
                    id="backup-password-confirmation"
                    spellCheck={false}
                    type={showPassword ? "text" : "password"}
                    {...backupForm.register("passwordConfirmation", {
                      validate: (value, values) =>
                        value === values.password || "Passwords must match.",
                    })}
                  />
                </Field>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
                <p className="text-xs leading-5 text-muted-foreground">
                  Unencrypted backups have checksums for integrity. Password-protected backups also
                  provide authenticated encryption.
                </p>
                <Button loading={createBackup.isPending} type="submit">
                  <ArchiveRestore aria-hidden="true" className="h-4 w-4" />
                  Create and verify backup
                </Button>
              </div>
            </form>
          </Panel>

          <Panel>
            <PanelHeader
              description="This removes the current workspace and local import/attachment files. Backups are preserved unless you explicitly include them."
              title="Delete local data"
            />
            <div className="flex flex-wrap items-center justify-between gap-4 p-5">
              <p className="max-w-prose text-sm leading-6 text-muted-foreground">
                This action is destructive and cannot be undone without a separate verified backup.
              </p>
              <Button onClick={() => setDeleteOpen(true)} type="button" variant="danger">
                <Trash2 aria-hidden="true" className="h-4 w-4" />
                Delete local data
              </Button>
            </div>
          </Panel>
        </div>

        <div className="space-y-5">
          <Panel>
            <PanelHeader title="Local system" />
            <dl className="space-y-3 p-4 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Application</dt>
                <dd className="font-medium">{system.data?.application}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Version</dt>
                <dd>{system.data?.version}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Storage</dt>
                <dd><Badge>{system.data?.storage}</Badge></dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Network</dt>
                <dd><Badge tone="success">loopback only</Badge></dd>
              </div>
            </dl>
          </Panel>

          <Panel>
            <PanelHeader title="Privacy status" />
            <ul className="space-y-4 p-4 text-sm">
              <li className="flex gap-3">
                <HardDrive aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" />
                <span className="min-w-0">Data directory <span className="block break-all font-medium">{privacy.data?.data_directory}</span></span>
              </li>
              <li className="flex gap-3">
                <WifiOff aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" />
                <span>Outbound guard {privacy.data?.outbound_guard_active ? "active" : "explicitly disabled"}.</span>
              </li>
              <li className="flex gap-3">
                <Database aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" />
                <span>Telemetry is off.</span>
              </li>
              <li className="flex gap-3">
                <ShieldCheck aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" />
                <span>Attachment limit {formatBytes(privacy.data?.max_attachment_bytes ?? 0)}.</span>
              </li>
              <li className="flex gap-3">
                <LockKeyhole aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" />
                <span>The privacy screen is not authentication or database encryption.</span>
              </li>
            </ul>
          </Panel>

          <Panel>
            <PanelHeader title="Last backup" />
            <div className="space-y-2 p-4 text-sm">
              {lastBackup ? (
                <>
                  <p className="break-all font-medium">{lastBackup.filename}</p>
                  <p className="text-muted-foreground">
                    {new Date(lastBackup.created_at).toLocaleString()} · {formatBytes(lastBackup.size_bytes)}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={lastBackup.encrypted ? "success" : "warning"}>
                      {lastBackup.encrypted ? "encrypted" : "not encrypted"}
                    </Badge>
                    <Badge tone={lastBackup.integrity_verified ? "success" : "neutral"}>
                      {lastBackup.integrity_verified ? "integrity verified" : "password needed to verify"}
                    </Badge>
                  </div>
                </>
              ) : (
                <p className="text-muted-foreground">No backup has been created yet.</p>
              )}
            </div>
          </Panel>
        </div>
      </div>

      <Modal
        description="Type the exact confirmation phrase. This is intentionally difficult to trigger by accident."
        onClose={() => {
          if (!deleteMutation.isPending) setDeleteOpen(false);
        }}
        open={deleteOpen}
        title="Delete all local workspace data?"
      >
        <form
          className="space-y-5"
          onSubmit={(event) => {
            event.preventDefault();
            if (deleteConfirmation === "DELETE ALL LOCAL DATA") deleteMutation.mutate();
          }}
        >
          <div className="rounded-md bg-destructive/10 p-4 text-sm leading-6 text-destructive">
            Tasks, notes, finance records, settings, attachments, and imported source files will be
            removed. The application will recreate an empty default workspace.
          </div>
          <Field
            hint="Enter DELETE ALL LOCAL DATA"
            id="delete-confirmation"
            label="Confirmation phrase"
            required
          >
            <Input
              autoComplete="off"
              id="delete-confirmation"
              onChange={(event) => setDeleteConfirmation(event.target.value)}
              spellCheck={false}
              value={deleteConfirmation}
            />
          </Field>
          <label className="flex min-h-10 items-start gap-3 text-sm" htmlFor="delete-backups">
            <input
              checked={includeBackups}
              className="mt-1 h-4 w-4 accent-foreground"
              id="delete-backups"
              onChange={(event) => setIncludeBackups(event.target.checked)}
              type="checkbox"
            />
            <span>
              Also delete local backup files
              <span className="block text-xs leading-5 text-muted-foreground">
                Leave this off if a backup may be needed for recovery.
              </span>
            </span>
          </label>
          <div className="flex justify-end gap-2 border-t border-border pt-4">
            <Button
              disabled={deleteMutation.isPending}
              onClick={() => setDeleteOpen(false)}
              type="button"
              variant="secondary"
            >
              Cancel
            </Button>
            <Button
              disabled={deleteConfirmation !== "DELETE ALL LOCAL DATA"}
              loading={deleteMutation.isPending}
              type="submit"
              variant="danger"
            >
              Delete confirmed data
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
