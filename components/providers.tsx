"use client";

import { EventStreamProvider } from "@/lib/event-stream-context";

export function Providers({ children }: { children: React.ReactNode }) {
  return <EventStreamProvider>{children}</EventStreamProvider>;
}
