import { Suspense } from "react";

import { SkeletonList } from "@/components/ui/states";
import { CommitmentsOverview } from "@/features/commitments/commitments-overview";

export default function CommitmentsPage() {
  return <Suspense fallback={<SkeletonList rows={7} />}><CommitmentsOverview /></Suspense>;
}
