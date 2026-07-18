"use client";

import type { components } from "@locallife/shared-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Beaker, Bell, Clock3, Play, Plus, Save, Trash2, Workflow } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form-controls";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { EmptyState, ErrorState, SkeletonList } from "@/components/ui/states";
import { getPreferences } from "@/lib/api/connected";
import { listAccounts, listCategories } from "@/lib/api/finance";
import {
  createAutomationRule,
  deleteAutomationRule,
  getSchedulerStatus,
  listAutomationExecutions,
  listAutomationRules,
  listLocalNotifications,
  previewAutomationRule,
  updateAutomationRule,
} from "@/lib/api/imports-automation";
import { listTags } from "@/lib/api/productivity";
import { queryKeys } from "@/lib/api/query-keys";
import type { AutomationRule, AutomationRuleCreate } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { useUiStore } from "@/stores/ui-store";

type TriggerType = components["schemas"]["AutomationTriggerType"];
type ActionType = components["schemas"]["AutomationActionType"];
type Operator = components["schemas"]["AutomationOperator"];

const triggerFields: Record<TriggerType, string[]> = {
  transaction_created: ["amount_minor", "currency_code", "payee", "transaction_type", "account_id", "category_id"],
  subscription_amount_changed: ["delta_minor", "delta_percent", "name", "new_amount_minor", "old_amount_minor", "currency_code"],
  event_created: ["title", "category", "location", "status", "timezone"],
  event_approaching: ["title", "category", "location", "status", "timezone", "minutes_until"],
  task_overdue: ["title", "status", "priority", "project_id", "overdue_days"],
  commitment_warning_created: ["commitment_title", "warning_code", "severity"],
  recurring_schedule: ["scheduled_at"],
};

const triggerLabels: Record<TriggerType, string> = {
  transaction_created: "Transaction created",
  subscription_amount_changed: "Subscription amount changed",
  event_created: "Event created",
  event_approaching: "Event approaching",
  task_overdue: "Task overdue",
  commitment_warning_created: "Commitment warning created",
  recurring_schedule: "Recurring schedule",
};

const actionLabels: Record<ActionType, string> = {
  create_task: "Create task",
  create_note: "Create note",
  create_planned_transaction: "Create planned transaction",
  add_tag: "Add tag",
  create_notification: "Create local notification",
  request_local_backup_reminder: "Request local backup reminder",
};

function parseConditionValue(value: string): string | number | boolean {
  if (value === "true") return true;
  if (value === "false") return false;
  const number = Number(value);
  return value.trim() !== "" && Number.isFinite(number) ? number : value;
}

function executionTone(status: string): "danger" | "neutral" | "success" | "warning" {
  if (status === "succeeded") return "success";
  if (status === "failed") return "danger";
  return "warning";
}

export function AutomationWorkspace() {
  const client = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const rules = useQuery({ queryKey: queryKeys.automation.rules, queryFn: listAutomationRules });
  const executions = useQuery({ queryKey: queryKeys.automation.executions, queryFn: listAutomationExecutions });
  const notifications = useQuery({ queryKey: queryKeys.automation.notifications, queryFn: listLocalNotifications });
  const scheduler = useQuery({ queryKey: ["automation", "scheduler"], queryFn: getSchedulerStatus });
  const preferences = useQuery({ queryKey: queryKeys.system.preferences, queryFn: getPreferences });
  const accounts = useQuery({ queryKey: queryKeys.finance.accounts, queryFn: listAccounts });
  const categories = useQuery({ queryKey: queryKeys.finance.categories, queryFn: listCategories });
  const tags = useQuery({ queryKey: queryKeys.notes.tags, queryFn: listTags });

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = rules.data?.find((rule) => rule.id === selectedId) ?? null;
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [triggerType, setTriggerType] = useState<TriggerType>("transaction_created");
  const [conditionField, setConditionField] = useState("amount_minor");
  const [operator, setOperator] = useState<Operator>("greater_than_or_equal");
  const [conditionValue, setConditionValue] = useState("");
  const [lookaheadMinutes, setLookaheadMinutes] = useState("1440");
  const [frequency, setFrequency] = useState<"daily" | "interval" | "weekly">("weekly");
  const [intervalMinutes, setIntervalMinutes] = useState("10080");
  const [localTime, setLocalTime] = useState("18:30");
  const [timezone, setTimezone] = useState("Europe/Rome");
  const [weekday, setWeekday] = useState("4");
  const [actionType, setActionType] = useState<ActionType>("create_notification");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState<components["schemas"]["TaskPriority"]>("medium");
  const [dueInDays, setDueInDays] = useState("1");
  const [accountId, setAccountId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [transactionType, setTransactionType] = useState<"expense" | "income">("expense");
  const [amountMinor, setAmountMinor] = useState("");
  const [currency, setCurrency] = useState("EUR");
  const [daysFromTrigger, setDaysFromTrigger] = useState("0");
  const [tagId, setTagId] = useState("");
  const [testContext, setTestContext] = useState('{"amount_minor": 2500, "currency_code": "EUR"}');
  const [testResult, setTestResult] = useState<string | null>(null);
  const displayTimezone = preferences.data?.timezone || "UTC";
  const locale = preferences.data?.locale || "en";

  function loadRule(rule: AutomationRule) {
    setSelectedId(rule.id);
    setName(rule.name);
    setDescription(rule.description ?? "");
    setTriggerType(rule.trigger.type);
    const condition = rule.trigger.conditions?.[0];
    setConditionField(condition?.field ?? triggerFields[rule.trigger.type][0]);
    setOperator(condition?.operator ?? "equals");
    setConditionValue(condition ? String(condition.value ?? "") : "");
    setLookaheadMinutes(String(rule.trigger.lookahead_minutes ?? 1440));
    if (rule.trigger.schedule) {
      setFrequency(rule.trigger.schedule.frequency);
      setIntervalMinutes(String(rule.trigger.schedule.interval_minutes ?? 60));
      setLocalTime((rule.trigger.schedule.local_time ?? "18:30").slice(0, 5));
      setTimezone(rule.trigger.schedule.timezone);
      setWeekday(String(rule.trigger.schedule.weekdays?.[0] ?? 4));
    }
    setActionType(rule.action.type);
    setTitle(rule.action.title ?? "");
    setBody(rule.action.body ?? "");
    setPriority(rule.action.priority);
    setDueInDays(String(rule.action.due_in_days ?? 1));
    setAccountId(rule.action.account_id ?? "");
    setCategoryId(rule.action.category_id ?? "");
    setTransactionType(rule.action.transaction_type === "income" ? "income" : "expense");
    setAmountMinor(String(rule.action.amount_minor ?? ""));
    setCurrency(rule.action.currency_code ?? "EUR");
    setDaysFromTrigger(String(rule.action.days_from_trigger));
    setTagId(rule.action.tag_id ?? "");
  }

  function clearBuilder() {
    setSelectedId(null);
    setName("");
    setDescription("");
    setTriggerType("transaction_created");
    setConditionField("amount_minor");
    setConditionValue("");
    setActionType("create_notification");
    setTitle("");
    setBody("");
    setTestResult(null);
  }

  const payload = useMemo<AutomationRuleCreate | null>(() => {
    if (!name.trim()) return null;
    const needsTitle = actionType !== "add_tag" && actionType !== "create_planned_transaction";
    if (needsTitle && !title.trim()) return null;
    const conditions = conditionValue.trim()
      ? [{ field: conditionField, operator, value: parseConditionValue(conditionValue) }]
      : [];
    const schedule = triggerType === "recurring_schedule"
      ? {
          frequency,
          timezone,
          interval_minutes: frequency === "interval" ? Number(intervalMinutes) : null,
          local_time: frequency === "interval" ? null : `${localTime}:00`,
          weekdays: frequency === "weekly" ? [Number(weekday)] : [],
        }
      : null;
    const action: AutomationRuleCreate["action"] = {
      type: actionType,
      title: title || null,
      body: body || null,
      priority,
      due_in_days: actionType === "create_task" ? Number(dueInDays) : null,
      account_id: actionType === "create_planned_transaction" ? accountId || null : null,
      category_id: actionType === "create_planned_transaction" ? categoryId || null : null,
      transaction_type: actionType === "create_planned_transaction" ? transactionType : null,
      amount_minor: actionType === "create_planned_transaction" ? Number(amountMinor) : null,
      currency_code: actionType === "create_planned_transaction" ? currency : null,
      days_from_trigger: Number(daysFromTrigger),
      tag_id: actionType === "add_tag" ? tagId || null : null,
      target_entity_type: null,
      target_entity_id: null,
    };
    if (actionType === "create_planned_transaction" && (!accountId || !amountMinor)) return null;
    if (actionType === "add_tag" && !tagId) return null;
    return {
      name: name.trim(),
      description: description || null,
      enabled: selected?.enabled ?? true,
      trigger: {
        type: triggerType,
        conditions,
        schedule,
        lookahead_minutes: triggerType === "event_approaching" ? Number(lookaheadMinutes) : null,
      },
      action,
    };
  }, [accountId, actionType, amountMinor, body, categoryId, conditionField, conditionValue, currency, daysFromTrigger, description, dueInDays, frequency, intervalMinutes, localTime, lookaheadMinutes, name, operator, priority, selected?.enabled, tagId, timezone, title, transactionType, triggerType, weekday]);

  const refresh = async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.automation.all }),
      client.invalidateQueries({ queryKey: ["automation", "scheduler"] }),
      client.invalidateQueries({ queryKey: queryKeys.tasks.all }),
      client.invalidateQueries({ queryKey: queryKeys.notes.all }),
      client.invalidateQueries({ queryKey: queryKeys.finance.all }),
    ]);
  };
  const save = useMutation({
    mutationFn: async () => {
      if (!payload) throw new Error("Complete the required rule fields.");
      return selected
        ? updateAutomationRule(selected.id, { ...payload, revision: selected.revision })
        : createAutomationRule(payload);
    },
    onSuccess: async (rule) => {
      loadRule(rule);
      await refresh();
      pushToast({ title: selected ? "Rule updated" : "Rule created", description: "The structured rule is stored locally.", tone: "success" });
    },
    onError: (error) => pushToast({ title: "Couldn't save rule", description: error.message, tone: "error" }),
  });
  const remove = useMutation({
    mutationFn: async () => {
      if (!selected) return;
      await deleteAutomationRule(selected.id, selected.revision);
    },
    onSuccess: async () => {
      clearBuilder();
      await refresh();
      pushToast({ title: "Rule removed", tone: "success" });
    },
  });
  const toggle = useMutation({
    mutationFn: (rule: AutomationRule) => updateAutomationRule(rule.id, { revision: rule.revision, enabled: !rule.enabled }),
    onSuccess: refresh,
  });
  const test = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error("Save the rule before testing it.");
      const context = JSON.parse(testContext) as Record<string, string | number | boolean | null>;
      return previewAutomationRule(selected.id, { context, source_key: "manual-ui-preview" });
    },
    onSuccess: (result) => setTestResult(result.matched ? result.action?.description ?? "Matched" : "Conditions did not match"),
    onError: (error) => setTestResult(error instanceof Error ? error.message : "Preview failed"),
  });
  const demo = useMutation({
    mutationFn: () => createAutomationRule({
      name: "Friday local backup reminder",
      description: "Demo rule: remind me every Friday evening without contacting a remote service.",
      enabled: true,
      trigger: { type: "recurring_schedule", conditions: [], schedule: { frequency: "weekly", timezone: "Europe/Rome", interval_minutes: null, local_time: "18:30:00", weekdays: [4] }, lookahead_minutes: null },
      action: { type: "request_local_backup_reminder", title: "Create a LocalLife backup", body: "Store a fresh local backup in your chosen offline location.", priority: "medium", due_in_days: null, account_id: null, category_id: null, transaction_type: null, amount_minor: null, currency_code: null, days_from_trigger: 0, tag_id: null, target_entity_type: null, target_entity_id: null },
    }),
    onSuccess: async (rule) => { loadRule(rule); await refresh(); },
  });

  if (rules.isLoading || preferences.isLoading) return <SkeletonList rows={8} />;
  if (rules.isError || preferences.isError) return <ErrorState retry={() => void Promise.all([rules.refetch(), preferences.refetch()])} />;

  return (
    <div className="space-y-6">
      <PageHeader actions={<><Button loading={demo.isPending} onClick={() => demo.mutate()} type="button" variant="secondary"><Beaker aria-hidden="true" className="h-4 w-4" />Create demo rule</Button><Button onClick={clearBuilder} type="button"><Plus aria-hidden="true" className="h-4 w-4" />New rule</Button></>} description="Build deterministic local triggers and actions. Rules contain validated fields only—never scripts or arbitrary code." eyebrow="On-device workflows" title="Automation" />

      <div className="grid gap-5 xl:grid-cols-[19rem_1fr]">
        <aside aria-label="Automation rules">
          <Panel className="overflow-hidden">
            <PanelHeader description={`${rules.data?.length ?? 0} structured rules`} title="Rules" />
            {!rules.data?.length ? <EmptyState description="Create a rule or load the local demo reminder." title="No automation rules" /> : <ul className="divide-y divide-border">{rules.data.map((rule) => <li className={selectedId === rule.id ? "bg-accent" : ""} key={rule.id}><button className="w-full p-4 text-left hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring" onClick={() => loadRule(rule)} type="button"><span className="flex items-center justify-between gap-2"><span className="truncate text-sm font-medium">{rule.name}</span><Badge tone={rule.enabled ? "success" : "neutral"}>{rule.enabled ? "On" : "Off"}</Badge></span><span className="mt-1 block text-xs text-muted-foreground">{triggerLabels[rule.trigger.type]} · {rule.execution_count} runs</span></button></li>)}</ul>}
          </Panel>
        </aside>

        <section className="min-w-0 space-y-5" aria-label="Rule builder">
          <Panel>
            <PanelHeader action={selected ? <div className="flex gap-2"><Button loading={toggle.isPending} onClick={() => toggle.mutate(selected)} size="sm" type="button" variant="secondary">{selected.enabled ? "Disable" : "Enable"}</Button><Button aria-label="Delete rule" loading={remove.isPending} onClick={() => remove.mutate()} size="icon" type="button" variant="ghost"><Trash2 aria-hidden="true" className="h-4 w-4" /></Button></div> : null} description="Choose one trigger, optional conditions, and exactly one deterministic action." title={selected ? "Edit rule" : "New rule"} />
            <div className="grid gap-5 p-5 lg:grid-cols-2">
              <div className="space-y-4">
                <Field id="rule-name" label="Name" required><Input id="rule-name" onChange={(event) => setName(event.target.value)} placeholder="Review larger purchases" value={name} /></Field>
                <Field id="rule-description" label="Description"><Textarea id="rule-description" onChange={(event) => setDescription(event.target.value)} value={description} /></Field>
                <div className="rounded-lg border border-border p-4">
                  <p className="mb-4 flex items-center gap-2 text-sm font-semibold"><Workflow aria-hidden="true" className="h-4 w-4" />When</p>
                  <div className="space-y-4">
                    <Field id="trigger-type" label="Trigger"><Select id="trigger-type" onChange={(event) => { const next = event.target.value as TriggerType; setTriggerType(next); setConditionField(triggerFields[next][0]); }} value={triggerType}>{Object.entries(triggerLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select></Field>
                    {triggerType === "recurring_schedule" ? <div className="grid gap-4 sm:grid-cols-2"><Field id="schedule-frequency" label="Frequency"><Select id="schedule-frequency" onChange={(event) => setFrequency(event.target.value as typeof frequency)} value={frequency}><option value="interval">Interval</option><option value="daily">Daily</option><option value="weekly">Weekly</option></Select></Field><Field id="schedule-timezone" label="Timezone"><Input id="schedule-timezone" onChange={(event) => setTimezone(event.target.value)} value={timezone} /></Field>{frequency === "interval" ? <Field id="schedule-interval" label="Minutes"><Input id="schedule-interval" min="1" onChange={(event) => setIntervalMinutes(event.target.value)} type="number" value={intervalMinutes} /></Field> : <Field id="schedule-time" label="Local time"><Input id="schedule-time" onChange={(event) => setLocalTime(event.target.value)} type="time" value={localTime} /></Field>}{frequency === "weekly" ? <Field id="schedule-day" label="Weekday"><Select id="schedule-day" onChange={(event) => setWeekday(event.target.value)} value={weekday}>{["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((label, index) => <option key={label} value={index}>{label}</option>)}</Select></Field> : null}</div> : <><div className="grid gap-4 sm:grid-cols-2"><Field id="condition-field" label="Condition field"><Select id="condition-field" onChange={(event) => setConditionField(event.target.value)} value={conditionField}>{triggerFields[triggerType].map((field) => <option key={field} value={field}>{field.replaceAll("_", " ")}</option>)}</Select></Field><Field id="condition-operator" label="Operator"><Select id="condition-operator" onChange={(event) => setOperator(event.target.value as Operator)} value={operator}>{(["equals", "not_equals", "greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal", "contains"] as Operator[]).map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</Select></Field></div><Field id="condition-value" label="Value" hint="Leave blank to run for every matching trigger."><Input id="condition-value" onChange={(event) => setConditionValue(event.target.value)} value={conditionValue} /></Field>{triggerType === "event_approaching" ? <Field id="lookahead" label="Look ahead (minutes)"><Input id="lookahead" min="1" onChange={(event) => setLookaheadMinutes(event.target.value)} type="number" value={lookaheadMinutes} /></Field> : null}</>}
                  </div>
                </div>
              </div>

              <div className="space-y-4 rounded-lg border border-border p-4">
                <p className="flex items-center gap-2 text-sm font-semibold"><Play aria-hidden="true" className="h-4 w-4" />Then</p>
                <Field id="action-type" label="Action"><Select id="action-type" onChange={(event) => setActionType(event.target.value as ActionType)} value={actionType}>{Object.entries(actionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select></Field>
                {actionType !== "add_tag" ? <><Field id="action-title" label={actionType === "create_planned_transaction" ? "Payee" : "Title"} required={actionType !== "create_planned_transaction"}><Input id="action-title" onChange={(event) => setTitle(event.target.value)} value={title} /></Field><Field id="action-body" label="Details"><Textarea id="action-body" onChange={(event) => setBody(event.target.value)} value={body} /></Field></> : null}
                {actionType === "create_task" ? <div className="grid gap-4 sm:grid-cols-2"><Field id="task-priority" label="Priority"><Select id="task-priority" onChange={(event) => setPriority(event.target.value as typeof priority)} value={priority}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="urgent">Urgent</option></Select></Field><Field id="task-due" label="Due in days"><Input id="task-due" min="0" onChange={(event) => setDueInDays(event.target.value)} type="number" value={dueInDays} /></Field></div> : null}
                {actionType === "create_planned_transaction" ? <div className="grid gap-4 sm:grid-cols-2"><Field id="plan-account" label="Account" required><Select id="plan-account" onChange={(event) => setAccountId(event.target.value)} value={accountId}><option value="">Choose…</option>{accounts.data?.data.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field><Field id="plan-category" label="Category"><Select id="plan-category" onChange={(event) => setCategoryId(event.target.value)} value={categoryId}><option value="">None</option>{categories.data?.data.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field><Field id="plan-type" label="Type"><Select id="plan-type" onChange={(event) => setTransactionType(event.target.value as typeof transactionType)} value={transactionType}><option value="expense">Expense</option><option value="income">Income</option></Select></Field><Field id="plan-amount" label="Amount (minor units)" required><Input id="plan-amount" min="1" onChange={(event) => setAmountMinor(event.target.value)} type="number" value={amountMinor} /></Field><Field id="plan-currency" label="Currency"><Input id="plan-currency" maxLength={3} onChange={(event) => setCurrency(event.target.value.toUpperCase())} value={currency} /></Field><Field id="plan-days" label="Days from trigger"><Input id="plan-days" min="0" onChange={(event) => setDaysFromTrigger(event.target.value)} type="number" value={daysFromTrigger} /></Field></div> : null}
                {actionType === "add_tag" ? <Field id="action-tag" label="Tag" required><Select id="action-tag" onChange={(event) => setTagId(event.target.value)} value={tagId}><option value="">Choose…</option>{tags.data?.data.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}</Select></Field> : null}
                <Button className="w-full" disabled={!payload} loading={save.isPending} onClick={() => save.mutate()} type="button"><Save aria-hidden="true" className="h-4 w-4" />{selected ? "Save changes" : "Create rule"}</Button>
              </div>
            </div>
          </Panel>

          <Panel>
            <PanelHeader description="Provide sample trigger context. Test mode evaluates conditions and describes the action without writing anything." title="Test preview" />
            <div className="grid gap-4 p-5 lg:grid-cols-[1fr_auto] lg:items-end"><Field id="test-context" label="Sample context (JSON)"><Textarea className="font-mono text-xs" id="test-context" onChange={(event) => setTestContext(event.target.value)} spellCheck={false} value={testContext} /></Field><Button disabled={!selected} loading={test.isPending} onClick={() => test.mutate()} type="button" variant="secondary"><Beaker aria-hidden="true" className="h-4 w-4" />Run safe test</Button></div>{testResult ? <p className="border-t border-border px-5 py-4 text-sm" role="status">{testResult}</p> : null}
          </Panel>
        </section>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_20rem]">
        <Panel className="overflow-hidden"><PanelHeader description="Successes, skipped condition matches, and failures are kept locally with idempotency keys." title="Execution history" />{executions.isLoading ? <div className="p-5"><SkeletonList /></div> : executions.isError ? <div className="p-5"><ErrorState retry={() => void executions.refetch()} /></div> : !executions.data?.data.length ? <EmptyState description="Rule executions will appear here." title="No executions yet" /> : <div className="overflow-x-auto"><table className="w-full min-w-[40rem] text-left text-sm"><thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground"><tr><th className="px-5 py-3">Status</th><th className="px-5 py-3">Trigger</th><th className="px-5 py-3">Action</th><th className="px-5 py-3">Completed</th></tr></thead><tbody className="divide-y divide-border">{executions.data.data.map((item) => <tr key={item.id}><td className="px-5 py-3"><Badge tone={executionTone(item.status)}>{item.status}</Badge></td><td className="px-5 py-3">{triggerLabels[item.trigger_type]}</td><td className="px-5 py-3 text-muted-foreground">{actionLabels[item.action_type]}</td><td className="px-5 py-3 text-xs text-muted-foreground">{item.completed_at ? formatDateTime(item.completed_at, displayTimezone, {}, locale) : "—"}</td></tr>)}</tbody></table></div>}</Panel>
        <div className="space-y-5"><Panel className="p-5"><p className="flex items-center gap-2 text-sm font-semibold"><Clock3 aria-hidden="true" className="h-4 w-4" />Scheduler</p>{scheduler.isLoading ? <div className="mt-3"><SkeletonList rows={2} /></div> : scheduler.isError ? <div className="mt-3"><ErrorState retry={() => void scheduler.refetch()} /></div> : <><p className="mt-3 text-sm text-muted-foreground">{scheduler.data?.running ? `${scheduler.data.scheduled_rule_ids.length} recurring rules scheduled` : "Scheduler is stopped in this environment"}</p>{scheduler.data?.next_wakeup_at ? <p className="mt-2 text-xs text-muted-foreground">Next wakeup {formatDateTime(scheduler.data.next_wakeup_at, displayTimezone, {}, locale)}</p> : null}</>}</Panel><Panel className="p-5"><p className="flex items-center gap-2 text-sm font-semibold"><Bell aria-hidden="true" className="h-4 w-4" />Local notifications</p>{notifications.isLoading ? <div className="mt-3"><SkeletonList rows={2} /></div> : notifications.isError ? <div className="mt-3"><ErrorState retry={() => void notifications.refetch()} /></div> : <><p className="mt-3 text-2xl font-semibold tabular-nums">{notifications.data?.length ?? 0}</p><p className="mt-1 text-xs text-muted-foreground">Unread on this device</p></>}</Panel></div>
      </div>
    </div>
  );
}
