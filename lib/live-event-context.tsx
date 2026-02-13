"use client";

import { createContext, useContext } from "react";
import { useLiveStream } from "./use-live-stream";
import type { DashboardStats, InteractionEvent, LiveEvent } from "./types";

type LiveEventCallback = (event: LiveEvent) => void;

interface LiveEventState {
  stats: DashboardStats | null;
  connected: boolean;
  error: string | null;
  recentInteractions: InteractionEvent[];
  subscribe: (callback: LiveEventCallback) => () => void;
  refreshStats: () => void;
}

const LiveEventContext = createContext<LiveEventState>({
  stats: null,
  connected: false,
  error: null,
  recentInteractions: [],
  subscribe: () => () => {},
  refreshStats: () => {},
});

export function LiveEventProvider({ children }: { children: React.ReactNode }) {
  const state = useLiveStream();
  return (
    <LiveEventContext.Provider value={state}>
      {children}
    </LiveEventContext.Provider>
  );
}

export function useLiveEventContext() {
  return useContext(LiveEventContext);
}
