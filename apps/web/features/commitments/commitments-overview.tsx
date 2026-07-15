"use client";

import type { components } from "@locallife/shared-types";
import { useQueries, useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, CalendarRange, Clock3, Plus, WalletCards } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form-controls";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { EmptyState, ErrorState, SkeletonList } from "@/components/ui/states";
import { getCommitmentAssessment, getPreferences, listCommitments } from "@/lib/api/connected";
import { queryKeys } from "@/lib/api/query-keys";
import { formatDate, formatDuration, formatMoney } from "@/lib/format";

import { AssessmentStatus, CommitmentStatusBadge } from "./commitment-ui";
import { CommitmentWizard } from "./commitment-wizard";

type CommitmentStatus = components["schemas"]["CommitmentStatus"];

export function CommitmentsOverview() {
  const router = useRouter();
  const params = useSearchParams();
  const query = params.get("q") || "";
  const status = (params.get("status") || "") as CommitmentStatus | "";
  const filters = { q: query || undefined, status: status || undefined };
  const commitments = useQuery({ queryKey: queryKeys.commitments.list(filters), queryFn: () => listCommitments(filters) });
  const preferences = useQuery({ queryKey: queryKeys.system.preferences, queryFn: getPreferences });
  const assessments = useQueries({ queries: (commitments.data?.data || []).map((item) => ({ queryKey: queryKeys.commitments.assessment(item.id), queryFn: () => getCommitmentAssessment(item.id), staleTime: 30_000 })) });
  const assessmentMap = new Map(assessments.flatMap((result) => result.data ? [[result.data.commitment.id, result.data] as const] : []));
  const update = (key: string, value: string) => { const next = new URLSearchParams(params.toString()); if (value) next.set(key, value); else next.delete(key); router.replace(`/commitments?${next.toString()}`); };
  if (commitments.isLoading) return <SkeletonList rows={7} />;
  if (commitments.isError) return <ErrorState retry={() => void commitments.refetch()} />;
  const timezone = preferences.data?.timezone || "UTC";
  return <div className="space-y-6">
    <PageHeader eyebrow="Connected planning" title="Commitments" description="See the real time, money, dependency, schedule, goal, and deadline consequences of an obligation before you make it." actions={<><Button onClick={() => update("create", "1")} type="button"><Plus aria-hidden="true" className="h-4 w-4" />New commitment</Button><Link className="inline-flex min-h-10 items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href="/capacity"><CalendarRange aria-hidden="true" className="h-4 w-4" />Capacity</Link></>} />
    <Panel className="grid gap-4 p-4 sm:grid-cols-[1fr_12rem]"><Field id="commitment-search" label="Search commitments"><Input id="commitment-search" onChange={(event) => update("q", event.target.value)} placeholder="Berlin, laptop, Build Week…" type="search" value={query} /></Field><Field id="commitment-filter" label="Status"><Select id="commitment-filter" onChange={(event) => update("status", event.target.value)} value={status}><option value="">All statuses</option>{["draft", "planned", "active", "completed", "cancelled", "archived"].map((value) => <option key={value} value={value}>{value}</option>)}</Select></Field></Panel>
    {!commitments.data?.data.length ? <Panel><EmptyState action={<Button onClick={() => update("create", "1")} type="button">Create the first commitment</Button>} title="No commitments match" description="Start with OpenAI Build Week, a Berlin conference decision, or a laptop purchase. The wizard will connect the underlying records." /></Panel> : <div className="grid gap-4 xl:grid-cols-2">{commitments.data.data.map((item) => { const assessment = assessmentMap.get(item.id); return <Panel className="group p-5" key={item.id}><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><CommitmentStatusBadge status={item.status} />{item.category ? <span className="text-xs text-muted-foreground">{item.category}</span> : null}</div><h2 className="mt-3 text-lg font-semibold tracking-tight">{item.title}</h2>{item.description_markdown ? <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted-foreground">{item.description_markdown}</p> : null}</div>{assessment ? <AssessmentStatus compact label="Overall feasibility" level={assessment.overall_status} /> : <span className="h-5 w-20 animate-pulse rounded bg-muted" />}</div><dl className="mt-5 grid grid-cols-2 gap-3 border-y border-border py-4 text-sm sm:grid-cols-4"><div><dt className="flex items-center gap-1 text-xs text-muted-foreground"><CalendarRange aria-hidden="true" className="h-3.5 w-3.5" />Target</dt><dd className="mt-1 font-medium">{formatDate(item.target_end_at, timezone)}</dd></div><div><dt className="flex items-center gap-1 text-xs text-muted-foreground"><WalletCards aria-hidden="true" className="h-3.5 w-3.5" />Planned cost</dt><dd className="mt-1 font-medium tabular-nums">{item.planned_cost_minor !== null && item.currency_code ? formatMoney(item.planned_cost_minor, item.currency_code) : "Not set"}</dd></div><div><dt className="flex items-center gap-1 text-xs text-muted-foreground"><Clock3 aria-hidden="true" className="h-3.5 w-3.5" />Required time</dt><dd className="mt-1 font-medium tabular-nums">{formatDuration(item.time_capacity_requirement_minutes)}</dd></div><div><dt className="flex items-center gap-1 text-xs text-muted-foreground"><AlertTriangle aria-hidden="true" className="h-3.5 w-3.5" />Warnings</dt><dd className="mt-1 font-medium tabular-nums">{assessment?.warnings.length ?? "…"}</dd></div></dl>{assessment ? <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3"><AssessmentStatus compact label="Time" level={assessment.time_capacity_status.status} /><AssessmentStatus compact label="Finance" level={assessment.financial_capacity_status.status} /><AssessmentStatus compact label="Dependencies" level={assessment.dependency_status.status} /><AssessmentStatus compact label="Schedule" level={assessment.schedule_conflict_status.status} /><AssessmentStatus compact label="Goals" level={assessment.goal_impact_status.status} /><AssessmentStatus compact label="Deadline" level={assessment.deadline_status.status} /></div> : null}<div className="mt-5 flex items-center justify-between"><p className="text-xs text-muted-foreground">{item.links.length} linked record{item.links.length === 1 ? "" : "s"}</p><Link className="inline-flex min-h-10 items-center gap-2 rounded-md px-3 text-sm font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={`/commitments/${item.id}`}>Review impact <ArrowRight aria-hidden="true" className="h-4 w-4 transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none" /></Link></div></Panel>; })}</div>}
    <CommitmentWizard onClose={() => update("create", "")} onComplete={(id) => router.push(`/commitments/${id}`)} open={params.get("create") === "1"} />
  </div>;
}
