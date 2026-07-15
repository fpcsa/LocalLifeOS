"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CalendarDays,
  CheckSquare2,
  CircleDollarSign,
  FileText,
  FlaskConical,
  FolderKanban,
  Goal,
  Layers3,
  Search,
  Settings,
  SunMedium,
  Clock3,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { Input } from "@/components/ui/form-controls";
import { Modal } from "@/components/ui/modal";
import { SkeletonList } from "@/components/ui/states";
import { globalSearch } from "@/lib/api/connected";
import { queryKeys } from "@/lib/api/query-keys";
import { useUiStore } from "@/stores/ui-store";

const destinations = [
  { label: "Today", href: "/", icon: SunMedium },
  { label: "Tasks", href: "/tasks", icon: CheckSquare2 },
  { label: "Calendar", href: "/calendar", icon: CalendarDays },
  { label: "Notes", href: "/notes", icon: FileText },
  { label: "Finance", href: "/finance", icon: CircleDollarSign },
  { label: "Goals", href: "/goals", icon: Goal },
  { label: "Commitments", href: "/commitments", icon: Layers3 },
  { label: "Scenarios", href: "/scenarios", icon: FlaskConical },
  { label: "Timeline", href: "/timeline", icon: Clock3 },
  { label: "Settings", href: "/settings", icon: Settings },
] as const;

function ResultGroup({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={`search-${title}`} className="space-y-1">
      <h3 className="px-2 py-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground" id={`search-${title}`}>
        {title}
      </h3>
      {children}
    </section>
  );
}

export function CommandPalette() {
  const open = useUiStore((state) => state.commandPaletteOpen);
  const setOpen = useUiStore((state) => state.setCommandPaletteOpen);
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const router = useRouter();

  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(input.trim()), 180);
    return () => window.clearTimeout(timer);
  }, [input]);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(!open);
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, setOpen]);

  const search = useQuery({
    queryKey: queryKeys.search(query),
    queryFn: () => globalSearch(query),
    enabled: query.length >= 2,
  });
  const navigation = useMemo(
    () => destinations.filter((item) => item.label.toLowerCase().includes(input.toLowerCase())),
    [input],
  );
  const go = (href: string) => {
    setOpen(false);
    setInput("");
    router.push(href);
  };

  return (
    <Modal description="Navigate or search local entities." onClose={() => setOpen(false)} open={open} title="Command palette" wide>
      <div className="space-y-4">
        <div className="relative">
          <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <Input aria-label="Search and navigate" autoComplete="off" className="pl-9" onChange={(event) => setInput(event.target.value)} placeholder="Search tasks, notes, projects, commitments, transactions…" type="search" value={input} />
        </div>
        <div className="max-h-[55vh] space-y-4 overflow-y-auto">
          {navigation.length ? (
            <ResultGroup title="Navigate">
              {navigation.map(({ href, icon: Icon, label }) => (
                <button className="flex min-h-10 w-full items-center gap-3 rounded-md px-3 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" key={href} onClick={() => go(href)} type="button">
                  <Icon aria-hidden="true" className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </ResultGroup>
          ) : null}
          {search.isLoading ? <SkeletonList rows={3} /> : null}
          {search.data ? (
            <>
              {search.data.tasks.length ? <ResultGroup title="Tasks">{search.data.tasks.map((item) => <button className="flex min-h-10 w-full items-center rounded-md px-3 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" key={item.id} onClick={() => go(`/tasks?task=${item.id}`)} type="button">{item.title}</button>)}</ResultGroup> : null}
              {search.data.projects.length ? <ResultGroup title="Projects">{search.data.projects.map((item) => <button className="flex min-h-10 w-full items-center gap-2 rounded-md px-3 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" key={item.id} onClick={() => go(`/tasks?project=${item.id}`)} type="button"><FolderKanban aria-hidden="true" className="h-4 w-4" />{item.name}</button>)}</ResultGroup> : null}
              {search.data.notes.length ? <ResultGroup title="Notes">{search.data.notes.map((item) => <button className="flex min-h-10 w-full items-center rounded-md px-3 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" key={item.id} onClick={() => go(`/notes?note=${item.id}`)} type="button">{item.title}</button>)}</ResultGroup> : null}
              {search.data.commitments.length ? <ResultGroup title="Commitments">{search.data.commitments.map((item) => <button className="flex min-h-10 w-full items-center rounded-md px-3 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" key={item.id} onClick={() => go(`/commitments?commitment=${item.id}`)} type="button">{item.title}</button>)}</ResultGroup> : null}
              {search.data.transactions.length ? <ResultGroup title="Transactions">{search.data.transactions.map((item) => <button className="flex min-h-10 w-full items-center rounded-md px-3 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" key={item.id} onClick={() => go(`/finance?transaction=${item.id}`)} type="button">{item.payee || item.note || "Transaction"}</button>)}</ResultGroup> : null}
            </>
          ) : null}
          {query.length >= 2 && search.data && Object.values(search.data).every((items) => items.length === 0) ? (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">No local results match “{query}”.</p>
          ) : null}
        </div>
      </div>
    </Modal>
  );
}
