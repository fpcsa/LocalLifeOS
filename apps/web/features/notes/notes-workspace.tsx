"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Download, FileUp, Link2, Plus, Search, Unlink } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useDeferredValue, useRef, useState } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form-controls";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { EmptyState, ErrorState, SkeletonList } from "@/components/ui/states";
import { getPreferences } from "@/lib/api/connected";
import {
  addNoteLink,
  attachmentDownloadUrl,
  createNote,
  getNote,
  listAttachments,
  listNotes,
  listTags,
  removeNoteLink,
  updateNote,
  uploadAttachment,
} from "@/lib/api/productivity";
import { queryKeys } from "@/lib/api/query-keys";
import type { Note, Tag } from "@/lib/api/types";
import { localDateKey } from "@/lib/date-range";
import { formatDateTime } from "@/lib/format";
import { useUiStore } from "@/stores/ui-store";

interface EditorValues {
  title: string;
  markdown: string;
  dailyNoteDate: string;
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function NoteEditor({ note, notes, tags, timezone }: { note: Note; notes: Note[]; tags: Tag[]; timezone: string }) {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const fileInput = useRef<HTMLInputElement>(null);
  const [tagIds, setTagIds] = useState<string[]>(note.tag_ids);
  const [linkTarget, setLinkTarget] = useState("");
  const [linkLabel, setLinkLabel] = useState("");
  const { register, handleSubmit, reset, formState: { errors, isDirty } } = useForm<EditorValues>({ defaultValues: { title: note.title, markdown: note.markdown, dailyNoteDate: note.daily_note_date || "" } });
  const attachments = useQuery({ queryKey: queryKeys.notes.attachments(note.id), queryFn: () => listAttachments(note.id) });
  const refreshNote = async () => { await Promise.all([queryClient.invalidateQueries({ queryKey: queryKeys.notes.detail(note.id) }), queryClient.invalidateQueries({ queryKey: queryKeys.notes.all })]); };
  const save = useMutation({ mutationFn: (values: EditorValues) => updateNote(note.id, { revision: note.revision, title: values.title, markdown: values.markdown, daily_note_date: values.dailyNoteDate || null, tag_ids: tagIds }), onSuccess: async (saved) => { queryClient.setQueryData(queryKeys.notes.detail(note.id), saved); await queryClient.invalidateQueries({ queryKey: queryKeys.notes.all }); reset({ title: saved.title, markdown: saved.markdown, dailyNoteDate: saved.daily_note_date || "" }); pushToast({ title: "Note saved", tone: "success" }); }, onError: (error) => pushToast({ title: "Couldn't save note", description: error instanceof Error ? error.message : "Reload and try again.", tone: "error" }) });
  const upload = useMutation({ mutationFn: (file: File) => uploadAttachment(file, "note", note.id), onSuccess: async () => { await Promise.all([queryClient.invalidateQueries({ queryKey: queryKeys.notes.attachments(note.id) }), refreshNote()]); if (fileInput.current) fileInput.current.value = ""; pushToast({ title: "Attachment stored locally", tone: "success" }); }, onError: (error) => pushToast({ title: "Couldn't attach file", description: error instanceof Error ? error.message : "Check the filename and file size.", tone: "error" }) });
  const link = useMutation({ mutationFn: () => addNoteLink(note.id, { target_note_id: linkTarget, label: linkLabel || null }), onSuccess: async () => { setLinkTarget(""); setLinkLabel(""); await refreshNote(); pushToast({ title: "Note linked", tone: "success" }); }, onError: (error) => pushToast({ title: "Couldn't link note", description: error instanceof Error ? error.message : "Choose a different note.", tone: "error" }) });
  const unlink = useMutation({ mutationFn: (linkId: string) => removeNoteLink(note.id, linkId), onSuccess: refreshNote, onError: (error) => pushToast({ title: "Couldn't remove link", description: error instanceof Error ? error.message : "Try again.", tone: "error" }) });
  const noteName = (id: string) => notes.find((item) => item.id === id)?.title || id;
  return (
    <div className="space-y-5">
      <form className="space-y-4" onSubmit={handleSubmit((values) => save.mutate(values))}>
        <div className="flex flex-wrap items-start justify-between gap-3"><p className="text-xs text-muted-foreground">Updated {formatDateTime(note.updated_at, timezone)}{isDirty ? " · Unsaved changes" : ""}</p><Button loading={save.isPending} size="sm" type="submit">Save note</Button></div>
        <Field error={errors.title?.message} id="note-title" label="Title" required><Input aria-invalid={!!errors.title} id="note-title" {...register("title", { required: "Enter a note title." })} /></Field>
        <Field id="note-daily-date" label="Daily note date"><Input id="note-daily-date" type="date" {...register("dailyNoteDate")} /></Field>
        <Field id="note-markdown" label="Markdown"><Textarea className="min-h-72 font-mono text-sm leading-6" id="note-markdown" spellCheck {...register("markdown")} /></Field>
        {tags.length ? <fieldset><legend className="mb-2 text-sm font-medium">Tags</legend><div className="flex flex-wrap gap-2">{tags.map((tag) => <label className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-full border border-border px-3 text-sm focus-within:ring-2 focus-within:ring-ring" key={tag.id}><input checked={tagIds.includes(tag.id)} className="h-4 w-4 accent-current" onChange={() => setTagIds((current) => current.includes(tag.id) ? current.filter((id) => id !== tag.id) : [...current, tag.id])} type="checkbox" />{tag.name}</label>)}</div></fieldset> : null}
      </form>
      <Panel>
        <PanelHeader title="Links & backlinks" description="Links are directional; backlinks show notes that point here." />
        <div className="space-y-4 p-4">
          <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]"><Select aria-label="Note to link" onChange={(event) => setLinkTarget(event.target.value)} value={linkTarget}><option value="">Choose a note</option>{notes.filter((item) => item.id !== note.id).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</Select><Input aria-label="Link label" onChange={(event) => setLinkLabel(event.target.value)} placeholder="Optional label" value={linkLabel} /><Button disabled={!linkTarget} loading={link.isPending} onClick={() => link.mutate()} type="button" variant="secondary"><Link2 aria-hidden="true" className="h-4 w-4" />Link</Button></div>
          {!note.links.length && !note.backlinks.length ? <p className="text-sm text-muted-foreground">No note links yet.</p> : <div className="grid gap-4 md:grid-cols-2"><div><h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Links from this note</h3><ul className="space-y-2">{note.links.map((item) => <li className="flex min-h-10 items-center justify-between gap-3 rounded-lg bg-muted px-3 text-sm" key={item.id}><span>{item.label || noteName(item.target_note_id)}</span><Button aria-label={`Remove link to ${noteName(item.target_note_id)}`} onClick={() => unlink.mutate(item.id)} size="icon" type="button" variant="ghost"><Unlink aria-hidden="true" className="h-4 w-4" /></Button></li>)}</ul></div><div><h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Backlinks</h3><ul className="space-y-2">{note.backlinks.map((item) => <li className="rounded-lg bg-muted px-3 py-2 text-sm" key={item.id}>{item.label || noteName(item.source_note_id)}</li>)}</ul></div></div>}
        </div>
      </Panel>
      <Panel>
        <PanelHeader title="Related records" description="Generic local links to tasks, projects, goals, commitments, and other records." />
        {!note.entity_links.length && !note.commitment_ids.length ? <EmptyState title="No related records" description="Related records added through the API will appear here." /> : <ul className="flex flex-wrap gap-2 p-4">{note.entity_links.map((item) => <li key={item.id}><Badge>{item.entity_type}: {item.entity_id.slice(0, 8)}</Badge></li>)}{note.commitment_ids.map((id) => <li key={id}><Badge>commitment: {id.slice(0, 8)}</Badge></li>)}</ul>}
      </Panel>
      <Panel>
        <PanelHeader title="Attachments" description="Files stay in the configured local attachment directory." action={<><input className="sr-only" onChange={(event) => { const file = event.target.files?.[0]; if (file) upload.mutate(file); }} ref={fileInput} type="file" /><Button loading={upload.isPending} onClick={() => fileInput.current?.click()} size="sm" type="button" variant="secondary"><FileUp aria-hidden="true" className="h-4 w-4" />Attach file</Button></>} />
        {attachments.isLoading ? <div className="p-4"><SkeletonList rows={2} /></div> : attachments.isError ? <div className="p-4"><ErrorState retry={() => void attachments.refetch()} /></div> : !attachments.data?.data.length ? <EmptyState title="No attachments" description="Attach a local document, image, or other supported file." /> : <ul className="divide-y divide-border">{attachments.data.data.map((item) => <li className="flex min-h-14 items-center justify-between gap-4 px-4 py-3" key={item.id}><div className="min-w-0"><p className="truncate text-sm font-medium">{item.original_filename}</p><p className="text-xs text-muted-foreground">{formatBytes(item.size_bytes)} · {item.media_type}</p></div><a aria-label={`Download ${item.original_filename}`} className="inline-flex h-10 w-10 items-center justify-center rounded-md hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={attachmentDownloadUrl(item.id)}><Download aria-hidden="true" className="h-4 w-4" /></a></li>)}</ul>}
      </Panel>
    </div>
  );
}

export function NotesWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";
  const deferredQuery = useDeferredValue(query);
  const selectedId = searchParams.get("note") || "";
  const openQuickCreate = useUiStore((state) => state.openQuickCreate);
  const pushToast = useUiStore((state) => state.pushToast);
  const filters = { q: deferredQuery || undefined, page_size: 100, sort: deferredQuery ? "relevance" as const : "updated_at" as const, order: "desc" as const };
  const notes = useQuery({ queryKey: queryKeys.notes.list(filters), queryFn: () => listNotes(filters) });
  const selected = useQuery({ queryKey: queryKeys.notes.detail(selectedId), queryFn: () => getNote(selectedId), enabled: !!selectedId });
  const tags = useQuery({ queryKey: queryKeys.notes.tags, queryFn: listTags });
  const preferences = useQuery({ queryKey: queryKeys.system.preferences, queryFn: getPreferences });
  const updateParams = (changes: Record<string, string | null>) => { const next = new URLSearchParams(searchParams.toString()); Object.entries(changes).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key)); router.replace(`/notes?${next.toString()}`); };
  const daily = useMutation({ mutationFn: async () => { const date = localDateKey(new Date(), preferences.data?.timezone || "UTC"); const existing = await listNotes({ daily_note_date: date, page_size: 1 }); return existing.data[0] || createNote({ title: `Daily note · ${date}`, markdown: "", daily_note_date: date }); }, onSuccess: (note) => updateParams({ note: note.id }), onError: (error) => pushToast({ title: "Couldn't open daily note", description: error instanceof Error ? error.message : "Try again.", tone: "error" }) });
  return (
    <div className="space-y-6">
      <PageHeader title="Notes" description="Search local Markdown, connect ideas with backlinks, and keep files beside their context." actions={<><Button loading={daily.isPending} onClick={() => daily.mutate()} type="button" variant="secondary"><CalendarDays aria-hidden="true" className="h-4 w-4" />Daily note</Button><Button onClick={() => openQuickCreate("note")} type="button"><Plus aria-hidden="true" className="h-4 w-4" />New note</Button></>} />
      <div className="grid min-h-[42rem] gap-5 xl:grid-cols-[20rem_minmax(0,1fr)]">
        <Panel className="overflow-hidden">
          <div className="border-b border-border p-3"><div className="relative"><Search aria-hidden="true" className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" /><Input aria-label="Search note contents" className="pl-9" onChange={(event) => updateParams({ q: event.target.value || null })} placeholder="Search title and Markdown" type="search" value={query} /></div></div>
          {notes.isLoading ? <div className="p-3"><SkeletonList rows={7} /></div> : notes.isError ? <div className="p-3"><ErrorState retry={() => void notes.refetch()} /></div> : !notes.data?.data.length ? <EmptyState title="No notes found" description="Create a note or try a different search." /> : <ul className="divide-y divide-border">{notes.data.data.map((note) => <li key={note.id}><button aria-current={selectedId === note.id ? "page" : undefined} className="min-h-16 w-full px-4 py-3 text-left hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring aria-[current=page]:bg-muted" onClick={() => updateParams({ note: note.id })} type="button"><span className="block truncate text-sm font-medium">{note.title}</span><span className="mt-1 block truncate text-xs text-muted-foreground">{note.daily_note_date || note.markdown || "Empty note"}</span></button></li>)}</ul>}
        </Panel>
        <Panel className="p-4 sm:p-6">
          {!selectedId ? <EmptyState title="Select a note" description="Choose a note from the list to edit Markdown, tags, links, and attachments." /> : selected.isLoading ? <SkeletonList rows={8} /> : selected.isError ? <ErrorState retry={() => void selected.refetch()} /> : selected.data ? <NoteEditor key={selected.data.id} note={selected.data} notes={notes.data?.data || []} tags={tags.data?.data || []} timezone={preferences.data?.timezone || "UTC"} /> : null}
        </Panel>
      </div>
    </div>
  );
}
