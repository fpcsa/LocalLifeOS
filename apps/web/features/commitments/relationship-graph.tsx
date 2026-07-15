"use client";

import type { components } from "@locallife/shared-types";
import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { useMemo } from "react";

import { entityHref } from "./commitment-ui";

type Commitment = components["schemas"]["CommitmentResponse"];
type Warning = components["schemas"]["CommitmentWarning"];

export function RelationshipGraph({ commitment, warnings }: { commitment: Commitment; warnings: Warning[] }) {
  const warningIds = useMemo(() => new Set(warnings.flatMap((warning) => warning.contributing_entities.map((entity) => `${entity.entity_type}:${entity.entity_id}`))), [warnings]);
  const { nodes, edges } = useMemo(() => {
    const center: Node = { id: `commitment:${commitment.id}`, position: { x: 280, y: 140 }, data: { label: commitment.title }, style: { background: "hsl(var(--primary))", color: "hsl(var(--primary-foreground))", border: "1px solid hsl(var(--primary))", borderRadius: 10, fontWeight: 600, padding: 14, width: 220 } };
    const linkNodes: Node[] = commitment.links.map((link, index) => {
      const key = `${link.entity_type}:${link.entity_id}`;
      const left = index % 2 === 0;
      return { id: key, position: { x: left ? 0 : 580, y: 24 + Math.floor(index / 2) * 112 }, data: { label: `${link.entity_type.replaceAll("_", " ")}${link.role ? ` · ${link.role}` : ""}` }, ariaLabel: `${link.entity_type.replaceAll("_", " ")} linked to ${commitment.title}${warningIds.has(key) ? ", contributes to a warning" : ""}`, style: { background: "hsl(var(--card))", color: "hsl(var(--foreground))", border: `1px solid hsl(var(--${warningIds.has(key) ? "warning" : "border"}))`, borderRadius: 10, padding: 12, width: 190 } };
    });
    const linkEdges: Edge[] = commitment.links.map((link) => { const key = `${link.entity_type}:${link.entity_id}`; return { id: `${commitment.id}-${key}`, source: key, target: center.id, animated: false, markerEnd: { type: MarkerType.ArrowClosed }, style: { stroke: warningIds.has(key) ? "hsl(var(--warning))" : "hsl(var(--muted-foreground))" } }; });
    return { nodes: [center, ...linkNodes], edges: linkEdges };
  }, [commitment, warningIds]);
  if (!commitment.links.length) return <div className="flex min-h-72 items-center justify-center rounded-lg bg-muted px-6 text-center text-sm text-muted-foreground">Link tasks, events, notes, money, or goals to reveal the commitment graph.</div>;
  return <div className="h-[30rem] overflow-hidden rounded-lg bg-muted" aria-label={`Relationship graph for ${commitment.title}`}><ReactFlow colorMode="system" edges={edges} edgesFocusable fitView minZoom={0.55} nodes={nodes} nodesDraggable={false} nodesFocusable onNodeClick={(_, node) => { if (node.id.startsWith("commitment:")) return; const [type, id] = node.id.split(":"); window.location.href = entityHref(type, id); }} proOptions={{ hideAttribution: true }}><Background color="hsl(var(--border))" gap={24} size={1} /><Controls showInteractive={false} /></ReactFlow></div>;
}
