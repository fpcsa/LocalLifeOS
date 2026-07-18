import type { components } from "@locallife/shared-types";
import { AlertTriangle, CheckCircle2, Circle, XCircle } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";

type AssessmentLevel = components["schemas"]["AssessmentLevel"];

export function assessmentTone(level: AssessmentLevel): "danger" | "neutral" | "success" | "warning" {
  if (level === "critical") return "danger";
  if (level === "warning") return "warning";
  if (level === "ok") return "success";
  return "neutral";
}

export function AssessmentStatus({ level, label, compact = false }: { level: AssessmentLevel; label: string; compact?: boolean }) {
  const Icon = level === "critical" ? XCircle : level === "warning" ? AlertTriangle : level === "ok" ? CheckCircle2 : Circle;
  return <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", level === "critical" ? "text-destructive" : level === "warning" ? "text-warning" : level === "ok" ? "text-success" : "text-muted-foreground")} title={`${label}: ${level.replaceAll("_", " ")}`}><Icon aria-hidden="true" className="h-3.5 w-3.5" />{compact ? <span className="sr-only">{label}: </span> : <span>{label}</span>}<span className={compact ? "sr-only" : "text-muted-foreground"}>{level.replaceAll("_", " ")}</span></span>;
}

export function CommitmentStatusBadge({ status }: { status: string }) {
  const tone = status === "active" || status === "completed" ? "success" : status === "cancelled" || status === "archived" ? "danger" : status === "planned" ? "warning" : "neutral";
  return <Badge tone={tone}>{status.replaceAll("_", " ")}</Badge>;
}

export function entityHref(type: string, id: string): string {
  if (type === "task") return `/tasks?task=${id}`;
  if (type === "calendar_event") return `/calendar?event=${id}`;
  if (type === "note") return `/notes?note=${id}`;
  if (type === "transaction") return `/finance#record-${id}`;
  if (type === "planned_transaction") return "/finance#reports";
  if (type === "goal" || type === "savings_goal") return `/goals#goal-${id}`;
  if (type === "project") return `/tasks?project=${id}`;
  if (type === "commitment") return `/commitments/${id}`;
  return "/timeline";
}

export function EntityLink({ type, id, label }: { type: string; id: string; label?: string }) {
  return <Link className="rounded-sm font-medium text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={entityHref(type, id)}>{label || `${type.replaceAll("_", " ")} · ${id.slice(0, 8)}`}</Link>;
}
