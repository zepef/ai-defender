"use client";

import { useReducer, useEffect, useRef, useCallback } from "react";
import { Canvas } from "@react-three/fiber";
import { useLiveEventContext } from "@/lib/live-event-context";
import type { LiveEvent, Session } from "@/lib/types";
import { SceneSetup } from "./scene-setup";
import { HoneypotCore } from "./honeypot-core";
import { SessionNodes, type SessionNodeData } from "./session-nodes";
import { ConnectionEdges } from "./connection-edges";
import { SessionLabels } from "./session-labels";
import { ParticleSystem, type ParticleSystemHandle } from "./particle-system";
import { StatsOverlay } from "./overlays/stats-overlay";
import { EventFeedOverlay } from "./overlays/event-feed-overlay";
import { SessionDetailPanel } from "./overlays/session-detail-panel";
import { SessionsListOverlay } from "./overlays/sessions-list-overlay";
import { PromptMonitorOverlay } from "./overlays/prompt-monitor-overlay";
import { useTTSAnnouncer } from "@/lib/use-tts-announcer";

// --- State management ---

interface VisualizationState {
  sessions: Map<string, SessionNodeData>;
  selectedSessionId: string | null;
}

type Action =
  | { type: "INIT"; sessions: Session[] }
  | { type: "SESSION_NEW"; session_id: string; client_info: Record<string, string>; escalation_level: number; timestamp: string }
  | { type: "SESSION_UPDATE"; session_id: string; escalation_level: number; interaction_count: number }
  | { type: "INTERACTION"; session_id: string; escalation_level: number }
  | { type: "SELECT_SESSION"; session_id: string | null };

function reducer(state: VisualizationState, action: Action): VisualizationState {
  switch (action.type) {
    case "INIT": {
      const sessions = new Map<string, SessionNodeData>();
      for (const s of action.sessions) {
        sessions.set(s.id, {
          session_id: s.id,
          escalation_level: s.escalation_level,
          interaction_count: s.interaction_count,
          client_info: s.client_info,
          timestamp: s.started_at,
        });
      }
      return { ...state, sessions };
    }
    case "SESSION_NEW": {
      const sessions = new Map(state.sessions);
      sessions.set(action.session_id, {
        session_id: action.session_id,
        escalation_level: action.escalation_level,
        interaction_count: 0,
        client_info: action.client_info,
        timestamp: action.timestamp,
      });
      return { ...state, sessions };
    }
    case "SESSION_UPDATE": {
      const existing = state.sessions.get(action.session_id);
      if (!existing) return state;
      const sessions = new Map(state.sessions);
      sessions.set(action.session_id, {
        ...existing,
        escalation_level: action.escalation_level,
        interaction_count: action.interaction_count,
      });
      return { ...state, sessions };
    }
    case "INTERACTION": {
      const existing = state.sessions.get(action.session_id);
      if (!existing) return state;
      const sessions = new Map(state.sessions);
      sessions.set(action.session_id, {
        ...existing,
        interaction_count: existing.interaction_count + 1,
        escalation_level: action.escalation_level,
      });
      return { ...state, sessions };
    }
    case "SELECT_SESSION":
      return { ...state, selectedSessionId: action.session_id };
    default:
      return state;
  }
}

// --- Component ---

export function AttackVisualization() {
  const [state, dispatch] = useReducer(reducer, {
    sessions: new Map(),
    selectedSessionId: null,
  });

  const { stats, connected, recentInteractions, subscribe } = useLiveEventContext();
  const particleRef = useRef<ParticleSystemHandle | null>(null);

  useTTSAnnouncer(subscribe);

  // Load initial sessions
  useEffect(() => {
    fetch("/api/sessions?limit=200")
      .then((r) => r.json())
      .then((data) => {
        if (data.sessions) {
          dispatch({ type: "INIT", sessions: data.sessions });
        }
      })
      .catch(() => {});
  }, []);

  // Subscribe to live events imperatively
  useEffect(() => {
    const unsubscribe = subscribe((event: LiveEvent) => {
      switch (event.type) {
        case "session_new":
          dispatch({
            type: "SESSION_NEW",
            session_id: event.data.session_id,
            client_info: event.data.client_info,
            escalation_level: event.data.escalation_level,
            timestamp: event.data.timestamp,
          });
          break;
        case "session_update":
          dispatch({
            type: "SESSION_UPDATE",
            session_id: event.data.session_id,
            escalation_level: event.data.escalation_level,
            interaction_count: event.data.interaction_count,
          });
          break;
        case "interaction":
          dispatch({
            type: "INTERACTION",
            session_id: event.data.session_id,
            escalation_level: event.data.escalation_level,
          });
          // Particle spawning would happen here if we had session 3D positions
          break;
      }
    });
    return unsubscribe;
  }, [subscribe]);

  const handleSelect = useCallback((id: string) => {
    dispatch({ type: "SELECT_SESSION", session_id: id });
  }, []);

  const handleDeselect = useCallback(() => {
    dispatch({ type: "SELECT_SESSION", session_id: null });
  }, []);

  const handleParticleReady = useCallback((handle: ParticleSystemHandle) => {
    particleRef.current = handle;
  }, []);

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-black">
      {/* 3D Canvas */}
      <Canvas
        camera={{ position: [0, 12, 20], fov: 55 }}
        gl={{ antialias: true, alpha: false }}
        onClick={(e) => {
          // Deselect on background click
          if (e.target === e.currentTarget) {
            handleDeselect();
          }
        }}
      >
        <color attach="background" args={["#050510"]} />
        <fog attach="fog" args={["#050510", 30, 60]} />

        <SceneSetup />
        <HoneypotCore />
        <SessionNodes
          sessions={state.sessions}
          selectedId={state.selectedSessionId}
          onSelect={handleSelect}
        />
        <ConnectionEdges sessions={state.sessions} />
        <SessionLabels sessions={state.sessions} selectedId={state.selectedSessionId} />
        <ParticleSystem onReady={handleParticleReady} />
      </Canvas>

      {/* HTML Overlays */}
      <StatsOverlay stats={stats} connected={connected} />
      <EventFeedOverlay interactions={recentInteractions} />

      {state.selectedSessionId ? (
        <SessionDetailPanel
          sessionId={state.selectedSessionId}
          onClose={handleDeselect}
        />
      ) : (
        <SessionsListOverlay
          sessions={state.sessions}
          selectedId={state.selectedSessionId}
          onSelect={handleSelect}
        />
      )}

      <PromptMonitorOverlay />

      {/* Floating nav button */}
      <NavButton />
    </div>
  );
}

function NavButton() {
  return (
    <a
      href="/stats"
      className="fixed bottom-6 right-6 z-20 bg-zinc-950/70 backdrop-blur-xl border border-white/10 rounded-xl px-4 py-2.5 text-sm text-zinc-300 hover:text-white hover:border-white/20 transition-all flex items-center gap-2"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <line x1="4" y1="6" x2="20" y2="6" />
        <line x1="4" y1="12" x2="20" y2="12" />
        <line x1="4" y1="18" x2="20" y2="18" />
      </svg>
      Dashboard
    </a>
  );
}
