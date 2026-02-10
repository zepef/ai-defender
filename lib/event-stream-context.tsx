"use client";

import { createContext, useContext } from "react";
import { useEventStream } from "./use-event-stream";
import type { DashboardStats } from "./types";

interface EventStreamState {
  stats: DashboardStats | null;
  connected: boolean;
  error: string | null;
}

const EventStreamContext = createContext<EventStreamState>({
  stats: null,
  connected: false,
  error: null,
});

export function EventStreamProvider({ children }: { children: React.ReactNode }) {
  const state = useEventStream();
  return (
    <EventStreamContext.Provider value={state}>
      {children}
    </EventStreamContext.Provider>
  );
}

export function useEventStreamContext() {
  return useContext(EventStreamContext);
}
