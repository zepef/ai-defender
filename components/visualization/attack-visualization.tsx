"use client";

import { useReducer, useEffect, useRef, useCallback, useState } from "react";
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
  | { type: "RESET" }
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
    case "RESET":
      return { sessions: new Map(), selectedSessionId: null };
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

  const { stats, connected, recentInteractions, subscribe, refreshStats } = useLiveEventContext();
  const particleRef = useRef<ParticleSystemHandle | null>(null);
  const [ttsMuted, setTtsMuted] = useState(false);

  useTTSAnnouncer(subscribe, ttsMuted);

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

  const [resetKey, setResetKey] = useState(0);

  const handleReset = useCallback(() => {
    dispatch({ type: "RESET" });
    refreshStats();
    setResetKey((k) => k + 1);
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }, [refreshStats]);

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

      <PromptMonitorOverlay key={resetKey} />

      {/* Control bar */}
      <ControlBar onReset={handleReset} ttsMuted={ttsMuted} onToggleTts={() => setTtsMuted((m) => !m)} />

      {/* Floating nav button */}
      <NavButton />
    </div>
  );
}

function ControlBar({ onReset, ttsMuted, onToggleTts }: { onReset: () => void; ttsMuted: boolean; onToggleTts: () => void }) {
  const [count, setCount] = useState(3);
  const [loading, setLoading] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [demo, setDemo] = useState(false);

  const handleLaunch = async () => {
    setLoading(true);
    try {
      await fetch("/api/admin/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ count, demo }),
      });
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (!confirmReset) {
      setConfirmReset(true);
      return;
    }
    setLoading(true);
    setConfirmReset(false);
    try {
      await fetch("/api/admin/reset", { method: "POST" });
      onReset();
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  // Cancel confirmation after 3 seconds
  useEffect(() => {
    if (!confirmReset) return;
    const timer = setTimeout(() => setConfirmReset(false), 3000);
    return () => clearTimeout(timer);
  }, [confirmReset]);

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 bg-zinc-950/70 backdrop-blur-xl border border-white/10 rounded-xl px-3 py-2">
      {/* Reset button */}
      <button
        disabled={loading}
        onClick={handleReset}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all disabled:opacity-40 ${
          confirmReset
            ? "bg-red-500/30 text-red-300 border border-red-500/40"
            : "text-red-400 hover:bg-red-500/20 border border-transparent hover:border-red-500/30"
        }`}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        </svg>
        {confirmReset ? "Confirm?" : "Reset"}
      </button>

      <div className="w-px h-6 bg-white/10" />

      {/* Count input */}
      <input
        type="number"
        min={1}
        max={20}
        value={count}
        onChange={(e) => setCount(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
        disabled={loading}
        className="w-14 bg-zinc-800/60 border border-white/10 rounded-lg px-2 py-1.5 text-sm text-center text-zinc-200 focus:outline-none focus:border-white/25 disabled:opacity-40"
      />

      {/* Launch button */}
      <button
        disabled={loading}
        onClick={handleLaunch}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-emerald-400 hover:bg-emerald-500/20 border border-transparent hover:border-emerald-500/30 transition-all disabled:opacity-40"
      >
        {loading ? (
          <svg className="animate-spin" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" stroke="none">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
        )}
        Launch
      </button>

      <div className="w-px h-6 bg-white/10" />

      {/* Demo mode toggle */}
      <label className="flex items-center gap-1.5 cursor-pointer text-sm text-zinc-400 hover:text-zinc-200 transition-colors select-none">
        <input
          type="checkbox"
          checked={demo}
          onChange={() => setDemo((d) => !d)}
          className="sr-only peer"
        />
        <div className="w-4 h-4 rounded border border-white/20 peer-checked:bg-amber-600 peer-checked:border-amber-500 flex items-center justify-center transition-all">
          {demo && (
            <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          )}
        </div>
        Demo
      </label>

      {/* TTS mute toggle */}
      <label className="flex items-center gap-1.5 cursor-pointer text-sm text-zinc-400 hover:text-zinc-200 transition-colors select-none">
        <input
          type="checkbox"
          checked={ttsMuted}
          onChange={onToggleTts}
          className="sr-only peer"
        />
        <div className="w-4 h-4 rounded border border-white/20 peer-checked:bg-zinc-600 peer-checked:border-zinc-500 flex items-center justify-center transition-all">
          {ttsMuted && (
            <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          )}
        </div>
        Mute
      </label>
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
