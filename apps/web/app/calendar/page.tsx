import { Suspense } from "react";

import { SkeletonList } from "@/components/ui/states";
import { CalendarWorkspace } from "@/features/calendar/calendar-workspace";

export default function CalendarPage() {
  return (
    <Suspense fallback={<SkeletonList rows={7} />}>
      <CalendarWorkspace />
    </Suspense>
  );
}
