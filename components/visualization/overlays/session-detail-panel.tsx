"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { SessionDetail, Interaction } from "@/lib/types";

const glassPanel = "bg-zinc-950/70 backdrop-blur-xl border border-white/10 rounded-xl";

const ESCALATION_LABELS: Record<number, string> = {
  0: "None",
  1: "Low",
  2: "Medium",
  3: "High",
};

const ESCALATION_COLORS: Record<number, string> = {
  0: "text-emerald-400",
  1: "text-yellow-400",
  2: "text-orange-400",
  3: "text-red-400",
};

export function SessionDetailPanel({
  sessionId,
  onClose,
}: {
  sessionId: string;
  onClose: () => void;
}) {
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    Promise.all([
      fetch(`/api/sessions/${sessionId}`).then((r) => r.json()),
      fetch(`/api/sessions/${sessionId}/interactions?limit=20`).then((r) => r.json()),
    ]).then(([sessionData, interData]) => {
      if (cancelled) return;
      setSession(sessionData);
      setInteractions(interData.interactions ?? []);
      setLoading(false);
    }).catch(() => {
      if (!cancelled) setLoading(false);
    });

    return () => { cancelled = true; };
  }, [sessionId]);

  return (
    <div
      className={`fixed top-20 left-4 z-20 w-[384px] max-h-[calc(100vh-120px)] overflow-y-auto ${glassPanel} p-5 animate-in slide-in-from-left-4 duration-200`}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-zinc-300">Session Detail</h3>
        <button
          onClick={onClose}
          className="text-zinc-500 hover:text-zinc-300 transition-colors text-lg leading-none"
        >
          &times;
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-600 border-t-zinc-300" />
        </div>
      ) : session ? (
        <div className="space-y-4">
          {/* Session ID */}
          <div>
            <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Session ID</span>
            <p className="font-mono text-xs text-zinc-300 break-all">{session.id}</p>
          </div>

          {/* Escalation */}
          <div>
            <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Escalation</span>
            <p className={`text-sm font-medium ${ESCALATION_COLORS[session.escalation_level] ?? "text-zinc-300"}`}>
              Level {session.escalation_level} - {ESCALATION_LABELS[session.escalation_level] ?? "Unknown"}
            </p>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-2 gap-3">
            <MiniStat label="Interactions" value={session.interaction_count} />
            <MiniStat label="Tokens" value={session.token_count} />
          </div>

          {/* Client info */}
          {Object.keys(session.client_info).length > 0 && (
            <div>
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Client</span>
              <div className="mt-1 space-y-1">
                {Object.entries(session.client_info).map(([k, v]) => (
                  <div key={k} className="flex gap-2 text-xs">
                    <span className="text-zinc-500">{k}:</span>
                    <span className="text-zinc-300 truncate">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Timeline */}
          {interactions.length > 0 && (
            <div>
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Timeline</span>
              <div className="mt-2 space-y-2">
                {interactions.map((ix) => (
                  <div key={ix.id} className="flex items-start gap-2">
                    <div className="mt-1 h-1.5 w-1.5 rounded-full bg-zinc-600 flex-shrink-0" />
                    <div className="min-w-0">
                      <span className="text-xs font-mono text-zinc-400">
                        {ix.tool_name ?? ix.method}
                      </span>
                      {ix.escalation_delta > 0 && (
                        <span className="ml-2 text-[10px] text-red-400">
                          +{ix.escalation_delta}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Link to full page */}
          <Link
            href={`/sessions/${sessionId}`}
            className="block text-center text-xs text-blue-400 hover:text-blue-300 transition-colors mt-3"
          >
            View full details &rarr;
          </Link>
        </div>
      ) : (
        <p className="text-xs text-zinc-500">Session not found.</p>
      )}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-white/5 px-3 py-2">
      <span className="text-[10px] text-zinc-500 uppercase tracking-wider">{label}</span>
      <p className="font-mono text-lg text-zinc-200">{value}</p>
    </div>
  );
}
