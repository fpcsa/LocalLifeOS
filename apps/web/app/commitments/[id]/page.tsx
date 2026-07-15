import { Suspense } from "react";

import { SkeletonList } from "@/components/ui/states";
import { CommitmentDetail } from "@/features/commitments/commitment-detail";

export default async function CommitmentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Suspense fallback={<SkeletonList rows={8} />}><CommitmentDetail commitmentId={id} /></Suspense>;
}
