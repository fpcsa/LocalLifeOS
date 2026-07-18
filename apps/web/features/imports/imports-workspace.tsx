"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarArrowDown, Download, FileSpreadsheet, Upload } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form-controls";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { EmptyState, ErrorState, SkeletonList } from "@/components/ui/states";
import { getPreferences } from "@/lib/api/connected";
import { listAccounts, listCategories } from "@/lib/api/finance";
import {
  applyImport,
  downloadCalendarExport,
  listImportHistory,
  listMappingProfiles,
  mapCsvImport,
  previewCalendarImport,
  previewCsvImport,
} from "@/lib/api/imports-automation";
import { queryKeys } from "@/lib/api/query-keys";
import type { CsvMapping, ImportPreview, ImportRow } from "@/lib/api/types";
import { formatDateTime, formatMoney } from "@/lib/format";
import { useUiStore } from "@/stores/ui-store";

type CsvField =
  | "account"
  | "amount"
  | "category"
  | "credit"
  | "currency"
  | "date"
  | "debit"
  | "description"
  | "external_id";

const initialColumns: Record<CsvField, string> = {
  account: "",
  amount: "",
  category: "",
  credit: "",
  currency: "",
  date: "",
  debit: "",
  description: "",
  external_id: "",
};

function statusTone(status: string): "danger" | "neutral" | "success" | "warning" {
  if (status === "invalid") return "danger";
  if (status === "imported") return "success";
  if (status === "changed" || status === "duplicate") return "warning";
  return "neutral";
}

function selectedRows(preview: ImportPreview): Set<string> {
  return new Set(preview.rows.filter((row) => row.included).map((row) => row.id));
}

export function formatImportedAmount(amountMinor: unknown, currencyCode: unknown, locale = "en"): string {
  if (amountMinor === undefined || amountMinor === null) return "—";
  const amount = Number(amountMinor);
  const currency = typeof currencyCode === "string" ? currencyCode.trim().toUpperCase() : "";
  if (!Number.isFinite(amount) || !currency) return `${String(amountMinor)} minor units`;
  try {
    return formatMoney(amount, currency, locale);
  } catch {
    return `${String(amountMinor)} ${currency}`;
  }
}

function FilePicker({
  accept,
  id,
  label,
  onFile,
  pending,
}: {
  accept: string;
  id: string;
  label: string;
  onFile: (file: File) => void;
  pending: boolean;
}) {
  return (
    <label
      className="flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-background p-5 text-center hover:bg-muted focus-within:ring-2 focus-within:ring-ring"
      htmlFor={id}
    >
      <Upload aria-hidden="true" className="h-6 w-6 text-muted-foreground" />
      <span className="text-sm font-medium">{pending ? "Reading locally…" : label}</span>
      <span className="text-xs text-muted-foreground">The file stays on this device.</span>
      <input
        accept={accept}
        className="sr-only"
        disabled={pending}
        id={id}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
          event.target.value = "";
        }}
        type="file"
      />
    </label>
  );
}

function PreviewTable({
  preview,
  selection,
  onSelection,
  timezone,
  locale,
}: {
  preview: ImportPreview;
  selection: Set<string>;
  onSelection: (next: Set<string>) => void;
  timezone: string;
  locale: string;
}) {
  function toggle(row: ImportRow) {
    const next = new Set(selection);
    if (next.has(row.id)) next.delete(row.id);
    else next.add(row.id);
    onSelection(next);
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[48rem] text-left text-sm">
        <thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
          <tr>
            <th className="px-4 py-3">Include</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Date / start</th>
            <th className="px-4 py-3">Description</th>
            <th className="px-4 py-3 text-right">Amount</th>
            <th className="px-4 py-3">Review</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {preview.rows.map((row) => {
            const normalized = row.normalized_data;
            const dateValue = normalized.occurred_at ?? normalized.starts_at ?? normalized.all_day_start;
            const disabled = row.status === "invalid" || row.duplicate_kind === "exact";
            return (
              <tr key={row.id}>
                <td className="px-4 py-3">
                  <input
                    aria-label={`Include row ${row.row_number}`}
                    checked={selection.has(row.id)}
                    className="h-4 w-4 accent-foreground"
                    disabled={disabled}
                    onChange={() => toggle(row)}
                    type="checkbox"
                  />
                </td>
                <td className="px-4 py-3">
                  <Badge tone={statusTone(row.status)}>{row.status}</Badge>
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground">
                  {typeof dateValue === "string" && dateValue.includes("T")
                    ? formatDateTime(dateValue, timezone, {}, locale)
                    : String(dateValue ?? "—")}
                </td>
                <td className="max-w-xs px-4 py-3">
                  <span className="block truncate">
                    {String(normalized.description ?? normalized.title ?? row.raw_data.summary ?? "—")}
                  </span>
                </td>
                <td className="px-4 py-3 text-right font-medium tabular-nums">
                  {formatImportedAmount(normalized.amount_minor, normalized.currency_code, locale)}
                </td>
                <td className="max-w-xs px-4 py-3 text-xs text-muted-foreground">
                  {row.issues.map((issue) => issue.message).join(" · ") ||
                    (row.duplicate_kind ? `${row.duplicate_kind} duplicate` : "Ready")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ColumnSelect({
  columns,
  field,
  label,
  required,
  value,
  onChange,
}: {
  columns: string[];
  field: CsvField;
  label: string;
  required?: boolean;
  value: string;
  onChange: (field: CsvField, value: string) => void;
}) {
  return (
    <Field id={`csv-${field}`} label={label} required={required}>
      <Select
        id={`csv-${field}`}
        onChange={(event) => onChange(field, event.target.value)}
        value={value}
      >
        <option value="">Not mapped</option>
        {columns.map((column) => (
          <option key={column} value={column}>
            {column}
          </option>
        ))}
      </Select>
    </Field>
  );
}

export function ImportsWorkspace() {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const history = useQuery({ queryKey: queryKeys.imports.history, queryFn: listImportHistory });
  const preferences = useQuery({ queryKey: queryKeys.system.preferences, queryFn: getPreferences });
  const profiles = useQuery({ queryKey: queryKeys.imports.profiles, queryFn: listMappingProfiles });
  const accounts = useQuery({ queryKey: queryKeys.finance.accounts, queryFn: listAccounts });
  const categories = useQuery({ queryKey: queryKeys.finance.categories, queryFn: listCategories });
  const [calendarPreview, setCalendarPreview] = useState<ImportPreview | null>(null);
  const [calendarSelection, setCalendarSelection] = useState<Set<string>>(new Set());
  const [csvPreview, setCsvPreview] = useState<ImportPreview | null>(null);
  const [csvSelection, setCsvSelection] = useState<Set<string>>(new Set());
  const [columns, setColumns] = useState(initialColumns);
  const [defaultAccountId, setDefaultAccountId] = useState("");
  const [defaultCategoryId, setDefaultCategoryId] = useState("");
  const [dateFormat, setDateFormat] = useState("%d/%m/%Y");
  const [decimalSeparator, setDecimalSeparator] = useState<"." | ",">(".");
  const [profileName, setProfileName] = useState("");
  const timezone = preferences.data?.timezone || "UTC";
  const locale = preferences.data?.locale || "en";

  const refreshHistory = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.imports.history }),
      queryClient.invalidateQueries({ queryKey: queryKeys.imports.profiles }),
      queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all }),
      queryClient.invalidateQueries({ queryKey: queryKeys.finance.all }),
    ]);
  };

  const calendarUpload = useMutation({
    mutationFn: previewCalendarImport,
    onSuccess: (preview) => {
      setCalendarPreview(preview);
      setCalendarSelection(selectedRows(preview));
    },
    onError: (error) => pushToast({ title: "Calendar preview failed", description: error.message, tone: "error" }),
  });
  const csvUpload = useMutation({
    mutationFn: previewCsvImport,
    onSuccess: (preview) => {
      setCsvPreview(preview);
      setCsvSelection(selectedRows(preview));
      const lower = Object.fromEntries(
        (preview.columns ?? []).map((value) => [value.toLowerCase(), value]),
      );
      setColumns((current) => ({
        ...current,
        date: lower.date ?? current.date,
        description: lower.description ?? lower.payee ?? current.description,
        amount: lower.amount ?? current.amount,
        debit: lower.debit ?? current.debit,
        credit: lower.credit ?? current.credit,
        currency: lower.currency ?? current.currency,
      }));
      if (!defaultAccountId && accounts.data?.data[0]) setDefaultAccountId(accounts.data.data[0].id);
    },
    onError: (error) => pushToast({ title: "CSV preview failed", description: error.message, tone: "error" }),
  });

  const mappingPayload = useMemo<CsvMapping | null>(() => {
    if (!csvPreview || !columns.date || !columns.description || !defaultAccountId) return null;
    const usesAmount = Boolean(columns.amount);
    if (!usesAmount && !columns.debit && !columns.credit) return null;
    return {
      columns: {
        date: columns.date,
        description: columns.description,
        amount: usesAmount ? columns.amount : null,
        debit: usesAmount ? null : columns.debit || null,
        credit: usesAmount ? null : columns.credit || null,
        currency: columns.currency || null,
        account: columns.account || null,
        category: columns.category || null,
        external_id: columns.external_id || null,
      },
      date_format: dateFormat || null,
      decimal_separator: decimalSeparator,
      amount_positive_is_income: true,
      default_currency: columns.currency ? null : "EUR",
      default_account_id: columns.account ? null : defaultAccountId,
      default_category_id: columns.category ? null : defaultCategoryId || null,
      profile_name: profileName || null,
      save_profile: Boolean(profileName),
    };
  }, [columns, csvPreview, dateFormat, decimalSeparator, defaultAccountId, defaultCategoryId, profileName]);

  const mapMutation = useMutation({
    mutationFn: async () => {
      if (!csvPreview || !mappingPayload) throw new Error("Complete the required mapping first.");
      return mapCsvImport(csvPreview.batch.id, mappingPayload);
    },
    onSuccess: async (preview) => {
      setCsvPreview(preview);
      setCsvSelection(selectedRows(preview));
      await refreshHistory();
      pushToast({ title: "Columns mapped", description: "Review normalized rows before importing.", tone: "success" });
    },
    onError: (error) => pushToast({ title: "Mapping failed", description: error.message, tone: "error" }),
  });
  const calendarApply = useMutation({
    mutationFn: async () => {
      if (!calendarPreview) throw new Error("Preview a calendar first.");
      return applyImport("calendar", calendarPreview.batch.id, [...calendarSelection]);
    },
    onSuccess: async () => {
      await refreshHistory();
      pushToast({ title: "Calendar imported", description: "Selected events are now in your local calendar.", tone: "success" });
    },
    onError: (error) => pushToast({ title: "Calendar import failed", description: error.message, tone: "error" }),
  });
  const csvApply = useMutation({
    mutationFn: async () => {
      if (!csvPreview) throw new Error("Preview a CSV first.");
      return applyImport("csv", csvPreview.batch.id, [...csvSelection]);
    },
    onSuccess: async () => {
      await refreshHistory();
      pushToast({ title: "Transactions imported", description: "Selected rows were added once to the local ledger.", tone: "success" });
    },
    onError: (error) => pushToast({ title: "CSV import failed", description: error.message, tone: "error" }),
  });

  function setColumn(field: CsvField, value: string) {
    setColumns((current) => {
      const next = { ...current, [field]: value };
      if (field === "amount" && value) {
        next.debit = "";
        next.credit = "";
      }
      if ((field === "debit" || field === "credit") && value) next.amount = "";
      return next;
    });
  }

  function loadProfile(profileId: string) {
    const profile = profiles.data?.find((item) => item.id === profileId);
    if (!profile) return;
    setColumns({
      account: profile.columns.account ?? "",
      amount: profile.columns.amount ?? "",
      category: profile.columns.category ?? "",
      credit: profile.columns.credit ?? "",
      currency: profile.columns.currency ?? "",
      date: profile.columns.date ?? "",
      debit: profile.columns.debit ?? "",
      description: profile.columns.description ?? "",
      external_id: profile.columns.external_id ?? "",
    });
    setDateFormat(profile.date_format ?? "");
    setDecimalSeparator(profile.decimal_separator as "." | ",");
    setDefaultAccountId(profile.default_account_id ?? "");
    setDefaultCategoryId(profile.default_category_id ?? "");
    setProfileName("");
  }

  return (
    <div className="space-y-6">
      <PageHeader
        actions={<Button onClick={downloadCalendarExport} type="button" variant="secondary"><Download aria-hidden="true" className="h-4 w-4" />Export calendar</Button>}
        description="Preview local calendar and bank files, resolve uncertain rows, then apply an explicit selection. Nothing is sent elsewhere."
        eyebrow="Local data exchange"
        title="Imports"
      />

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel className="overflow-hidden">
          <PanelHeader description="Supports common iCalendar timezones and recurrence rules." title="Calendar (.ics)" />
          <div className="space-y-4 p-5">
            <FilePicker accept=".ics,text/calendar" id="calendar-file" label="Choose an .ics file" onFile={(file) => calendarUpload.mutate(file)} pending={calendarUpload.isPending} />
            {calendarPreview ? (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-muted-foreground">
                  {calendarPreview.batch.new_count} new · {calendarPreview.batch.changed_count} changed · {calendarPreview.batch.duplicate_count} duplicates · {calendarPreview.batch.invalid_count} invalid
                </p>
                <Button disabled={!calendarSelection.size || calendarPreview.batch.status === "applied"} loading={calendarApply.isPending} onClick={() => calendarApply.mutate()} type="button"><CalendarArrowDown aria-hidden="true" className="h-4 w-4" />Import {calendarSelection.size}</Button>
              </div>
            ) : null}
          </div>
          {calendarPreview ? <PreviewTable locale={locale} onSelection={setCalendarSelection} preview={calendarPreview} selection={calendarSelection} timezone={timezone} /> : null}
        </Panel>

        <Panel className="overflow-hidden">
          <PanelHeader description="Delimiter and encoding are detected conservatively before mapping." title="Bank statement (.csv)" />
          <div className="space-y-4 p-5">
            <FilePicker accept=".csv,text/csv" id="csv-file" label="Choose a bank CSV" onFile={(file) => csvUpload.mutate(file)} pending={csvUpload.isPending} />
            {csvPreview ? <p className="text-xs text-muted-foreground">Detected {csvPreview.batch.detected_encoding} · delimiter {JSON.stringify(csvPreview.batch.detected_delimiter)} · {csvPreview.batch.total_rows} rows</p> : null}
          </div>
        </Panel>
      </div>

      {csvPreview ? (
        <Panel>
          <PanelHeader description="Map the source once, save a reusable profile if useful, then inspect normalized values." title="CSV mapping and review" />
          <div className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4">
            <Field id="csv-saved-profile" label="Reuse saved profile">
              <Select id="csv-saved-profile" onChange={(event) => loadProfile(event.target.value)} value="">
                <option value="">Choose a profile…</option>
                {profiles.data?.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
              </Select>
            </Field>
            <ColumnSelect columns={csvPreview.columns ?? []} field="date" label="Date" onChange={setColumn} required value={columns.date} />
            <ColumnSelect columns={csvPreview.columns ?? []} field="description" label="Description" onChange={setColumn} required value={columns.description} />
            <ColumnSelect columns={csvPreview.columns ?? []} field="amount" label="Signed amount" onChange={setColumn} value={columns.amount} />
            <ColumnSelect columns={csvPreview.columns ?? []} field="debit" label="Debit" onChange={setColumn} value={columns.debit} />
            <ColumnSelect columns={csvPreview.columns ?? []} field="credit" label="Credit" onChange={setColumn} value={columns.credit} />
            <ColumnSelect columns={csvPreview.columns ?? []} field="currency" label="Currency" onChange={setColumn} value={columns.currency} />
            <ColumnSelect columns={csvPreview.columns ?? []} field="account" label="Account" onChange={setColumn} value={columns.account} />
            <ColumnSelect columns={csvPreview.columns ?? []} field="category" label="Category" onChange={setColumn} value={columns.category} />
            <ColumnSelect columns={csvPreview.columns ?? []} field="external_id" label="External ID" onChange={setColumn} value={columns.external_id} />
            <Field id="csv-default-account" label="Default account" required={!columns.account}>
              <Select disabled={Boolean(columns.account)} id="csv-default-account" onChange={(event) => setDefaultAccountId(event.target.value)} value={defaultAccountId}><option value="">Choose…</option>{accounts.data?.data.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</Select>
            </Field>
            <Field id="csv-default-category" label="Default category">
              <Select disabled={Boolean(columns.category)} id="csv-default-category" onChange={(event) => setDefaultCategoryId(event.target.value)} value={defaultCategoryId}><option value="">No default</option>{categories.data?.data.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</Select>
            </Field>
            <Field id="csv-date-format" label="Date format"><Input id="csv-date-format" onChange={(event) => setDateFormat(event.target.value)} placeholder="%d/%m/%Y" value={dateFormat} /></Field>
            <Field id="csv-decimal" label="Decimal separator"><Select id="csv-decimal" onChange={(event) => setDecimalSeparator(event.target.value as "." | ",")} value={decimalSeparator}><option value=".">Period (.)</option><option value=",">Comma (,)</option></Select></Field>
            <Field id="csv-profile-name" label="Save mapping as"><Input id="csv-profile-name" onChange={(event) => setProfileName(event.target.value)} placeholder="Optional profile name" value={profileName} /></Field>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4">
            <p className="text-xs text-muted-foreground">Saved profiles: {profiles.data?.map((profile) => profile.name).join(", ") || "none"}</p>
            <div className="flex gap-2"><Button disabled={!mappingPayload} loading={mapMutation.isPending} onClick={() => mapMutation.mutate()} type="button" variant="secondary"><FileSpreadsheet aria-hidden="true" className="h-4 w-4" />Normalize preview</Button><Button disabled={!csvSelection.size || !csvPreview.rows.some((row) => Object.keys(row.normalized_data).length)} loading={csvApply.isPending} onClick={() => csvApply.mutate()} type="button">Import {csvSelection.size}</Button></div>
          </div>
          <PreviewTable locale={locale} onSelection={setCsvSelection} preview={csvPreview} selection={csvSelection} timezone={timezone} />
        </Panel>
      ) : null}

      <Panel>
        <PanelHeader description="Each source fingerprint, preview result, and apply outcome remains available locally." title="Import history" />
        {history.isLoading || preferences.isLoading ? <div className="p-5"><SkeletonList rows={4} /></div> : history.isError || preferences.isError ? <div className="p-5"><ErrorState retry={() => void Promise.all([history.refetch(), preferences.refetch()])} /></div> : !history.data?.data.length ? <EmptyState description="Calendar and bank previews will appear here before anything is applied." title="No imports yet" /> : <div className="overflow-x-auto"><table className="w-full min-w-[44rem] text-left text-sm"><thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground"><tr><th className="px-5 py-3">File</th><th className="px-5 py-3">Kind</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Rows</th><th className="px-5 py-3">Created</th></tr></thead><tbody className="divide-y divide-border">{history.data.data.map((batch) => <tr key={batch.id}><td className="px-5 py-3 font-medium">{batch.original_filename}</td><td className="px-5 py-3 text-muted-foreground">{batch.kind.replaceAll("_", " ")}</td><td className="px-5 py-3"><Badge tone={batch.status === "applied" ? "success" : "neutral"}>{batch.status}</Badge></td><td className="px-5 py-3 tabular-nums">{batch.imported_count}/{batch.total_rows}</td><td className="px-5 py-3 text-xs text-muted-foreground">{formatDateTime(batch.created_at, timezone, {}, locale)}</td></tr>)}</tbody></table></div>}
      </Panel>
    </div>
  );
}
