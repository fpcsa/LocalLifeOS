import { Suspense } from "react";

import { SkeletonList } from "@/components/ui/states";
import { ScenariosWorkspace } from "@/features/scenarios/scenarios-workspace";

export default function ScenariosPage() { return <Suspense fallback={<SkeletonList rows={8} />}><ScenariosWorkspace /></Suspense>; }
