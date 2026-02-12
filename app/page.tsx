"use client";

import dynamic from "next/dynamic";
import { LiveEventProvider } from "@/lib/live-event-context";

const AttackVisualization = dynamic(
  () =>
    import("@/components/visualization/attack-visualization").then(
      (mod) => mod.AttackVisualization
    ),
  { ssr: false, loading: () => <LoadingScreen /> }
);

function LoadingScreen() {
  return (
    <div className="flex h-screen w-screen items-center justify-center bg-black">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
        <p className="text-sm text-zinc-500">Initializing 3D scene...</p>
      </div>
    </div>
  );
}

export default function LiveViewPage() {
  return (
    <LiveEventProvider>
      <AttackVisualization />
    </LiveEventProvider>
  );
}
