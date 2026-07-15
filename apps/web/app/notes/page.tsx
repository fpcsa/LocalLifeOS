import { Suspense } from "react";

import { SkeletonList } from "@/components/ui/states";
import { NotesWorkspace } from "@/features/notes/notes-workspace";

export default function NotesPage() {
  return (
    <Suspense fallback={<SkeletonList rows={8} />}>
      <NotesWorkspace />
    </Suspense>
  );
}
