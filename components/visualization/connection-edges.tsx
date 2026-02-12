"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import type { SessionNodeData } from "./session-nodes";

const ESCALATION_COLORS: Record<number, string> = {
  0: "#22c55e",
  1: "#eab308",
  2: "#f97316",
  3: "#ef4444",
};

const ESCALATION_RADIUS: Record<number, number> = {
  0: 10,
  1: 8,
  2: 6,
  3: 4,
};

function hashCode(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0;
  }
  return Math.abs(hash);
}

function Edge({ data, index }: { data: SessionNodeData; index: number }) {
  const ref = useRef<THREE.Group>(null);
  const angle = useMemo(
    () => (hashCode(data.session_id) % 1000) / 1000 * Math.PI * 2,
    [data.session_id]
  );
  const radius = ESCALATION_RADIUS[data.escalation_level] ?? 10;
  const color = ESCALATION_COLORS[data.escalation_level] ?? "#22c55e";

  const pointsRef = useRef<[number, number, number][]>([
    [0, 0, 0],
    [radius, 0, 0],
  ]);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const orbitSpeed = 0.1;
    const currentAngle = angle + t * orbitSpeed;
    const x = Math.cos(currentAngle) * radius;
    const z = Math.sin(currentAngle) * radius;
    const y = Math.sin(t * 0.5 + index) * 0.3;
    pointsRef.current = [
      [0, 0, 0],
      [x, y, z],
    ];
  });

  return (
    <Line
      points={pointsRef.current}
      color={color}
      lineWidth={0.5}
      transparent
      opacity={0.15}
    />
  );
}

export function ConnectionEdges({ sessions }: { sessions: Map<string, SessionNodeData> }) {
  const sessionArray = useMemo(() => Array.from(sessions.values()), [sessions]);

  return (
    <group>
      {sessionArray.map((s, i) => (
        <Edge key={s.session_id} data={s} index={i} />
      ))}
    </group>
  );
}
