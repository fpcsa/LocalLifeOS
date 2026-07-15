import { Suspense } from "react";

import { SkeletonList } from "@/components/ui/states";
import { TimelineWorkspace } from "@/features/timeline/timeline-workspace";

export default function TimelinePage() {
  return <Suspense fallback={<SkeletonList rows={8} />}><TimelineWorkspace /></Suspense>;
}
