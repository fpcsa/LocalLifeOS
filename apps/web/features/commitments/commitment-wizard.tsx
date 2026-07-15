"use client";

import type { components } from "@locallife/shared-types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronLeft, ChevronRight, Link2, Plus } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form-controls";
import { Modal } from "@/components/ui/modal";
import { createCalendarEvent, listCalendarEvents } from "@/lib/api/calendar";
import {
  addCommitmentLink,
  createCommitment,
  createGoal,
  getCommitmentAssessment,
  getCommitment,
  getPreferences,
  listGoals,
  updateCommitment,
} from "@/lib/api/connected";
import { createPlannedTransaction, listAccounts, listPlannedTransactions, listTransactions } from "@/lib/api/finance";
import { createNote, createTask, listNotes, listTasks } from "@/lib/api/productivity";
import { queryKeys } from "@/lib/api/query-keys";
import type { CommitmentAssessment } from "@/lib/api/types";
import { fromDateTimeLocal, majorToMinor } from "@/lib/format";
import { useUiStore } from "@/stores/ui-store";

import { AssessmentStatus } from "./commitment-ui";

type LinkType = components["schemas"]["CommitmentEntityType"];
type NewType = "calendar_event" | "goal" | "note" | "planned_transaction" | "task";
interface LinkCandidate { id: string; type: LinkType; label: string }

const steps = ["Basics", "Linked records", "Capacity & target", "Assessment"] as const;

function localInput(days = 1, hour = 9): string {
  const value = new Date(Date.now() + days * 86_400_000);
  value.setHours(hour, 0, 0, 0);
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 16);
}

export function CommitmentWizard({ open, onClose, onComplete }: { open: boolean; onClose: () => void; onComplete: (id: string) => void }) {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const [step, setStep] = useState(0);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("project");
  const [status, setStatus] = useState<"draft" | "planned">("planned");
  const [targetEnd, setTargetEnd] = useState(localInput(30, 18));
  const [decisionDeadline, setDecisionDeadline] = useState(localInput(14, 18));
  const [requiredMinutes, setRequiredMinutes] = useState("480");
  const [plannedCost, setPlannedCost] = useState("");
  const [financialBuffer, setFinancialBuffer] = useState("");
  const [currency, setCurrency] = useState("EUR");
  const [linkType, setLinkType] = useState<LinkType>("task");
  const [selected, setSelected] = useState<LinkCandidate[]>([]);
  const [newType, setNewType] = useState<NewType>("task");
  const [newTitle, setNewTitle] = useState("");
  const [newAmount, setNewAmount] = useState("");
  const [newDuration, setNewDuration] = useState("60");
  const [newStart, setNewStart] = useState(localInput(2, 10));
  const [newEnd, setNewEnd] = useState(localInput(2, 11));
  const [newAccountId, setNewAccountId] = useState("");
  const [assessment, setAssessment] = useState<CommitmentAssessment | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [calendarRange] = useState(() => {
    const now = Date.now();
    return {
      start: new Date(now - 365 * 86_400_000).toISOString(),
      end: new Date(now + 365 * 86_400_000).toISOString(),
    };
  });
  const preferences = useQuery({ queryKey: queryKeys.system.preferences, queryFn: getPreferences, enabled: open });
  const tasks = useQuery({ queryKey: queryKeys.tasks.list({ wizard: true }), queryFn: () => listTasks({ page_size: 100 }), enabled: open });
  const notes = useQuery({ queryKey: queryKeys.notes.list({ wizard: true }), queryFn: () => listNotes({ page_size: 100 }), enabled: open });
  const events = useQuery({ queryKey: queryKeys.calendar.events({ wizard: true }), queryFn: () => listCalendarEvents({ start: calendarRange.start, end: calendarRange.end }), enabled: open });
  const transactions = useQuery({ queryKey: queryKeys.finance.transactions({ wizard: true }), queryFn: () => listTransactions({ page_size: 100 }), enabled: open });
  const planned = useQuery({ queryKey: queryKeys.finance.planned({ wizard: true }), queryFn: () => listPlannedTransactions({ page_size: 100 }), enabled: open });
  const goals = useQuery({ queryKey: queryKeys.goals.list, queryFn: listGoals, enabled: open });
  const accounts = useQuery({ queryKey: queryKeys.finance.accounts, queryFn: listAccounts, enabled: open });

  const candidates = useMemo<LinkCandidate[]>(() => [
    ...(tasks.data?.data || []).map((item) => ({ id: item.id, type: "task" as const, label: item.title })),
    ...(events.data?.data || []).map((item) => ({ id: item.id, type: "calendar_event" as const, label: item.title })),
    ...(notes.data?.data || []).map((item) => ({ id: item.id, type: "note" as const, label: item.title })),
    ...(transactions.data?.data || []).map((item) => ({ id: item.id, type: "transaction" as const, label: item.payee || `${item.transaction_type} · ${item.amount_minor}` })),
    ...(planned.data || []).map((item) => ({ id: item.id, type: "planned_transaction" as const, label: item.payee || `Planned ${item.transaction_type}` })),
    ...(goals.data?.data || []).map((item) => ({ id: item.id, type: "goal" as const, label: item.title })),
  ], [events.data, goals.data, notes.data, planned.data, tasks.data, transactions.data]);
  const visibleCandidates = candidates.filter((candidate) => candidate.type === linkType);

  const createLinked = useMutation({
    mutationFn: async () => {
      if (!newTitle.trim()) throw new Error("Add a title for the linked record.");
      if (newType === "task") {
        const item = await createTask({ title: newTitle, status: "todo", priority: "medium", preferred_time_of_day: "any", estimated_duration_minutes: Number(newDuration) || null, commitment_ids: [], tag_ids: [] });
        return { id: item.id, type: "task" as const, label: item.title };
      }
      if (newType === "note") {
        const item = await createNote({ title: newTitle, markdown: "", commitment_ids: [], entity_links: [], tag_ids: [] });
        return { id: item.id, type: "note" as const, label: item.title };
      }
      if (newType === "goal") {
        const item = await createGoal({ title: newTitle, status: "active", progress_basis_points: 0 });
        return { id: item.id, type: "goal" as const, label: item.title };
      }
      if (newType === "calendar_event") {
        const startsAt = fromDateTimeLocal(newStart); const endsAt = fromDateTimeLocal(newEnd);
        if (!startsAt || !endsAt || new Date(endsAt) <= new Date(startsAt)) throw new Error("The event end must be after its start.");
        const item = await createCalendarEvent({ title: newTitle, status: "confirmed", all_day: false, starts_at: startsAt, ends_at: endsAt, timezone: preferences.data?.timezone || "UTC", preparation_buffer_minutes: 0, travel_buffer_minutes: 0, recovery_buffer_minutes: 0, commitment_ids: [], linked_entities: [] });
        return { id: item.id, type: "calendar_event" as const, label: item.title };
      }
      const account = accounts.data?.data.find((item) => item.id === newAccountId) || accounts.data?.data[0];
      if (!account) throw new Error("Create a financial account before adding a planned cost.");
      const plannedFor = fromDateTimeLocal(newStart);
      if (!plannedFor) throw new Error("Choose when the planned cost is expected.");
      const item = await createPlannedTransaction({ account_id: account.id, transaction_type: "expense", amount_minor: majorToMinor(newAmount, account.currency_code), currency_code: account.currency_code, planned_for: plannedFor, payee: newTitle, is_committed: true });
      return { id: item.id, type: "planned_transaction" as const, label: newTitle };
    },
    onSuccess: (candidate) => { setSelected((items) => items.some((item) => item.id === candidate.id && item.type === candidate.type) ? items : [...items, candidate]); setNewTitle(""); pushToast({ title: "Linked record created locally", tone: "success" }); void queryClient.invalidateQueries(); },
    onError: (error) => pushToast({ title: "Couldn't create linked record", description: error instanceof Error ? error.message : "Check the values and try again.", tone: "error" }),
  });

  const preview = useMutation({
    mutationFn: async () => {
      if (!title.trim()) throw new Error("Add a commitment title first.");
      const hasMoney = Boolean(plannedCost.trim() || financialBuffer.trim());
      const values = { title, description_markdown: description || null, status, category: category || null, target_end_at: fromDateTimeLocal(targetEnd) || null, decision_deadline_at: fromDateTimeLocal(decisionDeadline) || null, time_capacity_requirement_minutes: Number(requiredMinutes) || null, planned_cost_minor: plannedCost.trim() ? majorToMinor(plannedCost, currency) : null, financial_buffer_requirement_minor: financialBuffer.trim() ? majorToMinor(financialBuffer, currency) : null, currency_code: hasMoney ? currency.toUpperCase() : null };
      const commitment = draftId
        ? await getCommitment(draftId).then((current) => updateCommitment(draftId, { revision: current.revision, ...values }))
        : await createCommitment(values);
      if (!commitment) throw new Error("The saved draft could not be reopened.");
      if (!draftId) {
        await Promise.all(selected.map((item) => addCommitmentLink(commitment.id, { entity_type: item.type, entity_id: item.id, role: "required" })));
        setDraftId(commitment.id);
      }
      return getCommitmentAssessment(commitment.id);
    },
    onSuccess: (result) => { setAssessment(result); setStep(3); void queryClient.invalidateQueries({ queryKey: queryKeys.commitments.all }); },
    onError: (error) => pushToast({ title: "Couldn't calculate assessment", description: error instanceof Error ? error.message : "Check the commitment values and try again.", tone: "error" }),
  });

  const toggle = (candidate: LinkCandidate) => setSelected((items) => items.some((item) => item.id === candidate.id && item.type === candidate.type) ? items.filter((item) => item.id !== candidate.id || item.type !== candidate.type) : [...items, candidate]);
  const finish = () => { if (!draftId) return; pushToast({ title: "Commitment ready for review", tone: "success" }); onComplete(draftId); };

  return <Modal description="Build the obligation, connect its evidence, then inspect every feasibility component." onClose={onClose} open={open} title="New commitment" wide>
    <ol aria-label="Commitment creation progress" className="mb-6 grid grid-cols-4 gap-2">{steps.map((label, index) => <li className="space-y-2" key={label}><div className={`h-1 rounded-full ${index <= step ? "bg-primary" : "bg-muted"}`} /><p className={`text-xs ${index === step ? "font-semibold text-foreground" : "text-muted-foreground"}`}>{index + 1}. {label}</p></li>)}</ol>
    {step === 0 ? <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (!title.trim()) return; setStep(1); }}><Field id="commitment-title" label="Title" required><Input autoComplete="off" id="commitment-title" onChange={(event) => setTitle(event.target.value)} placeholder="OpenAI Build Week project" value={title} /></Field><Field id="commitment-description" label="Description"><Textarea id="commitment-description" onChange={(event) => setDescription(event.target.value)} placeholder="What you are committing to and why it matters." value={description} /></Field><div className="grid gap-4 sm:grid-cols-2"><Field id="commitment-category" label="Category"><Input id="commitment-category" onChange={(event) => setCategory(event.target.value)} placeholder="project" value={category} /></Field><Field id="commitment-status" label="Starting status"><Select id="commitment-status" onChange={(event) => setStatus(event.target.value as "draft" | "planned")} value={status}><option value="draft">Draft</option><option value="planned">Planned</option></Select></Field></div><div className="flex justify-end"><Button type="submit">Continue <ChevronRight aria-hidden="true" className="h-4 w-4" /></Button></div></form> : null}
    {step === 1 ? <div className="space-y-6"><fieldset className="space-y-3"><legend className="text-sm font-semibold">Link existing records</legend><div className="grid gap-3 sm:grid-cols-[12rem_1fr]"><Field id="link-type" label="Record type"><Select id="link-type" onChange={(event) => setLinkType(event.target.value as LinkType)} value={linkType}>{(["task", "calendar_event", "note", "transaction", "planned_transaction", "goal"] as LinkType[]).map((type) => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}</Select></Field><div className="max-h-52 overflow-y-auto rounded-lg border border-border p-2">{visibleCandidates.length ? visibleCandidates.map((candidate) => { const checked = selected.some((item) => item.id === candidate.id && item.type === candidate.type); return <label className="flex min-h-10 cursor-pointer items-center gap-3 rounded-md px-2 text-sm hover:bg-muted" key={`${candidate.type}:${candidate.id}`}><input checked={checked} className="h-4 w-4 accent-foreground" onChange={() => toggle(candidate)} type="checkbox" /><span className="truncate">{candidate.label}</span></label>; }) : <p className="p-3 text-sm text-muted-foreground">No {linkType.replaceAll("_", " ")} records yet. Create one below.</p>}</div></div></fieldset><fieldset className="space-y-4 rounded-lg bg-muted p-4"><legend className="px-1 text-sm font-semibold">Create a linked record</legend><div className="grid gap-4 sm:grid-cols-2"><Field id="new-link-type" label="Record type"><Select id="new-link-type" onChange={(event) => setNewType(event.target.value as NewType)} value={newType}><option value="task">Task</option><option value="calendar_event">Calendar event</option><option value="note">Note</option><option value="planned_transaction">Planned cost</option><option value="goal">Goal</option></Select></Field><Field id="new-link-title" label={newType === "planned_transaction" ? "Payee or purpose" : "Title"} required><Input id="new-link-title" onChange={(event) => setNewTitle(event.target.value)} value={newTitle} /></Field>{newType === "task" ? <Field id="new-link-duration" label="Estimate in minutes"><Input id="new-link-duration" inputMode="numeric" onChange={(event) => setNewDuration(event.target.value)} value={newDuration} /></Field> : null}{newType === "calendar_event" ? <><Field id="new-link-start" label="Starts"><Input id="new-link-start" onChange={(event) => setNewStart(event.target.value)} type="datetime-local" value={newStart} /></Field><Field id="new-link-end" label="Ends"><Input id="new-link-end" onChange={(event) => setNewEnd(event.target.value)} type="datetime-local" value={newEnd} /></Field></> : null}{newType === "planned_transaction" ? <><Field id="new-link-amount" label="Amount" required><Input id="new-link-amount" inputMode="decimal" onChange={(event) => setNewAmount(event.target.value)} placeholder="1250.00" value={newAmount} /></Field><Field id="new-link-account" label="Account"><Select id="new-link-account" onChange={(event) => setNewAccountId(event.target.value)} value={newAccountId}><option value="">Use first account</option>{accounts.data?.data.map((account) => <option key={account.id} value={account.id}>{account.name} · {account.currency_code}</option>)}</Select></Field><Field id="new-link-date" label="Planned for"><Input id="new-link-date" onChange={(event) => setNewStart(event.target.value)} type="datetime-local" value={newStart} /></Field></> : null}</div><Button loading={createLinked.isPending} onClick={() => createLinked.mutate()} type="button" variant="secondary"><Plus aria-hidden="true" className="h-4 w-4" />Create and select</Button></fieldset>{selected.length ? <div><p className="text-sm font-semibold">Selected · {selected.length}</p><ul className="mt-2 flex flex-wrap gap-2">{selected.map((item) => <li className="rounded-full bg-accent px-3 py-1 text-xs" key={`${item.type}:${item.id}`}><Link2 aria-hidden="true" className="mr-1 inline h-3 w-3" />{item.label}</li>)}</ul></div> : null}<div className="flex justify-between"><Button onClick={() => setStep(0)} type="button" variant="ghost"><ChevronLeft aria-hidden="true" className="h-4 w-4" />Back</Button><Button onClick={() => setStep(2)} type="button">Continue <ChevronRight aria-hidden="true" className="h-4 w-4" /></Button></div></div> : null}
    {step === 2 ? <form className="space-y-5" onSubmit={(event) => { event.preventDefault(); preview.mutate(); }}><div className="grid gap-4 sm:grid-cols-2"><Field id="target-end" label="Target date" required><Input id="target-end" onChange={(event) => setTargetEnd(event.target.value)} type="datetime-local" value={targetEnd} /></Field><Field id="decision-deadline" label="Decision deadline"><Input id="decision-deadline" onChange={(event) => setDecisionDeadline(event.target.value)} type="datetime-local" value={decisionDeadline} /></Field><Field id="required-minutes" label="Required time" hint="Minutes you need to protect for this commitment."><Input id="required-minutes" inputMode="numeric" onChange={(event) => setRequiredMinutes(event.target.value)} value={requiredMinutes} /></Field><Field id="currency" label="Currency"><Input id="currency" maxLength={3} onChange={(event) => setCurrency(event.target.value.toUpperCase())} spellCheck={false} value={currency} /></Field><Field id="planned-cost" label="Planned cost"><Input id="planned-cost" inputMode="decimal" onChange={(event) => setPlannedCost(event.target.value)} placeholder="0.00" value={plannedCost} /></Field><Field id="financial-buffer" label="Required remaining buffer"><Input id="financial-buffer" inputMode="decimal" onChange={(event) => setFinancialBuffer(event.target.value)} placeholder="0.00" value={financialBuffer} /></Field></div><div className="rounded-lg border border-border p-4 text-sm leading-6 text-muted-foreground">Preview saves a local draft before calculating. If you close afterward, the draft remains available so no linked work is lost.</div><div className="flex justify-between"><Button onClick={() => setStep(1)} type="button" variant="ghost"><ChevronLeft aria-hidden="true" className="h-4 w-4" />Back</Button><Button loading={preview.isPending} type="submit">Preview assessment</Button></div></form> : null}
    {step === 3 && assessment ? <div className="space-y-5"><div className="rounded-lg bg-muted p-5"><p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Deterministic assessment</p><h3 className="mt-2 text-xl font-semibold">{assessment.overall_status === "ok" ? "The current plan fits" : assessment.overall_status === "critical" ? "Critical constraints need review" : assessment.overall_status === "warning" ? "The plan has visible trade-offs" : "More linked evidence is needed"}</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">Every component stays visible below. LocalLife OS does not collapse these facts into an opaque score.</p></div><div className="grid gap-3 sm:grid-cols-2">{[["Time", assessment.time_capacity_status], ["Finance", assessment.financial_capacity_status], ["Dependencies", assessment.dependency_status], ["Schedule", assessment.schedule_conflict_status], ["Goals", assessment.goal_impact_status], ["Deadline", assessment.deadline_status]].map(([label, component]) => { const value = component as CommitmentAssessment["time_capacity_status"]; return <div className="rounded-lg border border-border p-4" key={label as string}><AssessmentStatus label={label as string} level={value.status} /><p className="mt-2 text-xs leading-5 text-muted-foreground">{value.summary}</p></div>; })}</div>{assessment.warnings.length ? <div><h3 className="text-sm font-semibold">Warnings</h3><ul className="mt-2 space-y-2">{assessment.warnings.map((warning) => <li className="rounded-lg border border-warning/40 bg-warning/5 p-3 text-sm" key={warning.code}>{warning.message}</li>)}</ul></div> : <p className="flex items-center gap-2 text-sm text-success"><Check aria-hidden="true" className="h-4 w-4" />No warnings from the linked records.</p>}<div className="flex justify-between"><Button onClick={() => setStep(2)} type="button" variant="ghost"><ChevronLeft aria-hidden="true" className="h-4 w-4" />Review inputs</Button><Button onClick={finish} type="button">Open commitment</Button></div></div> : null}
  </Modal>;
}
