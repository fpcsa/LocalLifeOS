import { Suspense } from "react";

import { SkeletonList } from "@/components/ui/states";
import { TasksWorkspace } from "@/features/tasks/tasks-workspace";

export default function TasksPage() {
  return <Suspense fallback={<SkeletonList rows={8} />}><TasksWorkspace /></Suspense>;
}
