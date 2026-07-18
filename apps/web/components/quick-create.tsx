"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form-controls";
import { Modal } from "@/components/ui/modal";
import { createCalendarEvent } from "@/lib/api/calendar";
import { getPreferences } from "@/lib/api/connected";
import { createTransaction, listAccounts } from "@/lib/api/finance";
import { createNote, createTask } from "@/lib/api/productivity";
import { queryKeys } from "@/lib/api/query-keys";
import { fromDateTimeLocal, majorToMinor } from "@/lib/format";
import { useUiStore, type QuickCreateKind } from "@/stores/ui-store";

interface QuickCreateValues {
  kind: QuickCreateKind;
  title: string;
  details: string;
  priority: "high" | "low" | "medium" | "urgent";
  duration: string;
  startsAt: string;
  endsAt: string;
  accountId: string;
  transactionType: "expense" | "income";
  amount: string;
  currency: string;
}

function defaults(kind: QuickCreateKind): QuickCreateValues {
  const start = new Date(Date.now() + 3_600_000);
  start.setMinutes(0, 0, 0);
  const end = new Date(start.getTime() + 3_600_000);
  const local = (date: Date) => new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
  return { kind, title: "", details: "", priority: "medium", duration: "30", startsAt: local(start), endsAt: local(end), accountId: "", transactionType: "expense", amount: "", currency: "EUR" };
}

export function QuickCreate() {
  const open = useUiStore((state) => state.quickCreateOpen);
  const kind = useUiStore((state) => state.quickCreateKind);
  const close = useUiStore((state) => state.closeQuickCreate);
  const pushToast = useUiStore((state) => state.pushToast);
  const queryClient = useQueryClient();
  const preferences = useQuery({ queryKey: queryKeys.system.preferences, queryFn: getPreferences });
  const accounts = useQuery({ queryKey: queryKeys.finance.accounts, queryFn: listAccounts, enabled: open });
  const { register, handleSubmit, reset, control, formState: { errors } } = useForm<QuickCreateValues>({ defaultValues: defaults(kind) });
  const selectedKind = useWatch({ control, name: "kind" });

  useEffect(() => reset(defaults(kind)), [kind, reset]);

  const mutation = useMutation({
    mutationFn: async (values: QuickCreateValues) => {
      if (values.kind === "task") return createTask({ title: values.title, description_markdown: values.details || null, priority: values.priority, estimated_duration_minutes: Number(values.duration) || null, status: "todo", preferred_time_of_day: "any" });
      if (values.kind === "note") return createNote({ title: values.title, markdown: values.details });
      if (values.kind === "event") return createCalendarEvent({ title: values.title, description_markdown: values.details || null, starts_at: fromDateTimeLocal(values.startsAt, preferences.data?.timezone || "UTC"), ends_at: fromDateTimeLocal(values.endsAt, preferences.data?.timezone || "UTC"), timezone: preferences.data?.timezone || "UTC", all_day: false, status: "confirmed", preparation_buffer_minutes: 0, travel_buffer_minutes: 0, recovery_buffer_minutes: 0 });
      return createTransaction({ account_id: values.accountId, transaction_type: values.transactionType, amount_minor: majorToMinor(values.amount, values.currency), currency_code: values.currency.toUpperCase(), occurred_at: new Date().toISOString(), payee: values.title, note: values.details || null });
    },
    onSuccess: async (_, values) => {
      await queryClient.invalidateQueries({ queryKey: values.kind === "task" ? queryKeys.tasks.all : values.kind === "note" ? queryKeys.notes.all : values.kind === "event" ? queryKeys.calendar.all : queryKeys.finance.all });
      pushToast({ title: `${values.kind[0].toUpperCase()}${values.kind.slice(1)} created`, tone: "success" });
      close();
      reset(defaults(values.kind));
    },
    onError: (error) => pushToast({ title: "Couldn't create item", description: error instanceof Error ? error.message : "Try again.", tone: "error" }),
  });

  return (
    <Modal description="Add a local item without leaving your current view." onClose={close} open={open} title="Quick create">
      <form className="space-y-4" onSubmit={handleSubmit((values) => mutation.mutate(values))}>
        <Field id="quick-kind" label="Type">
          <Select id="quick-kind" {...register("kind")}>
            <option value="task">Task</option><option value="event">Event</option><option value="note">Note</option><option value="transaction">Transaction</option>
          </Select>
        </Field>
        <Field error={errors.title?.message} id="quick-title" label={selectedKind === "transaction" ? "Payee" : "Title"} required>
          <Input aria-describedby={errors.title ? "quick-title-error" : undefined} aria-invalid={errors.title ? true : undefined} autoComplete="off" id="quick-title" {...register("title", { required: "Enter a title." })} />
        </Field>
        {selectedKind === "task" ? <div className="grid gap-4 sm:grid-cols-2"><Field id="quick-priority" label="Priority"><Select id="quick-priority" {...register("priority")}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option></Select></Field><Field id="quick-duration" label="Estimate" hint="Minutes"><Input id="quick-duration" inputMode="numeric" pattern="[0-9]*" {...register("duration")} /></Field></div> : null}
        {selectedKind === "event" ? <div className="grid gap-4 sm:grid-cols-2"><Field id="quick-start" label="Starts" required><Input id="quick-start" type="datetime-local" {...register("startsAt", { required: true })} /></Field><Field id="quick-end" label="Ends" required><Input id="quick-end" type="datetime-local" {...register("endsAt", { required: true })} /></Field></div> : null}
        {selectedKind === "transaction" ? <><Field id="quick-account" label="Account" required><Select id="quick-account" {...register("accountId", { required: true })}><option value="">Select account</option>{accounts.data?.data.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</Select></Field><div className="grid gap-4 sm:grid-cols-3"><Field id="quick-transaction-type" label="Type"><Select id="quick-transaction-type" {...register("transactionType")}><option value="expense">Expense</option><option value="income">Income</option></Select></Field><Field id="quick-amount" label="Amount" required><Input id="quick-amount" inputMode="decimal" placeholder="0.00" {...register("amount", { required: true })} /></Field><Field id="quick-currency" label="Currency"><Input autoCapitalize="characters" id="quick-currency" maxLength={3} {...register("currency")} /></Field></div></> : null}
        <Field id="quick-details" label={selectedKind === "note" ? "Markdown" : "Details"} hint="Stored only in your local workspace."><Textarea id="quick-details" {...register("details")} /></Field>
        <div className="flex justify-end gap-2"><Button onClick={close} type="button" variant="ghost">Cancel</Button><Button loading={mutation.isPending} type="submit">Create {selectedKind}</Button></div>
      </form>
    </Modal>
  );
}
