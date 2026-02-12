"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Instance, Instances } from "@react-three/drei";
import * as THREE from "three";

export interface SessionNodeData {
  session_id: string;
  escalation_level: number;
  interaction_count: number;
  client_info: Record<string, string>;
  timestamp: string;
}

const ESCALATION_COLORS: Record<number, string> = {
  0: "#22c55e", // green
  1: "#eab308", // yellow
  2: "#f97316", // orange
  3: "#ef4444", // red
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

function SessionNode({
  data,
  index,
  total,
  onClick,
  selected,
}: {
  data: SessionNodeData;
  index: number;
  total: number;
  onClick: (id: string) => void;
  selected: boolean;
}) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const angle = useMemo(() => {
    return (hashCode(data.session_id) % 1000) / 1000 * Math.PI * 2;
  }, [data.session_id]);

  const radius = ESCALATION_RADIUS[data.escalation_level] ?? 10;
  const color = ESCALATION_COLORS[data.escalation_level] ?? "#22c55e";
  const size = Math.min(0.3 + data.interaction_count * 0.05, 0.8);

  useFrame(({ clock }) => {
    if (ref.current) {
      const t = clock.getElapsedTime();
      const orbitSpeed = 0.1;
      const currentAngle = angle + t * orbitSpeed;
      const x = Math.cos(currentAngle) * radius;
      const z = Math.sin(currentAngle) * radius;
      const y = Math.sin(t * 0.5 + index) * 0.3;
      ref.current.position.set(x, y, z);
    }
  });

  return (
    <Instance
      ref={ref}
      scale={selected ? size * 1.5 : size}
      color={color}
      onClick={(e) => {
        e.stopPropagation();
        onClick(data.session_id);
      }}
    />
  );
}

export function SessionNodes({
  sessions,
  selectedId,
  onSelect,
}: {
  sessions: Map<string, SessionNodeData>;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const sessionArray = useMemo(() => Array.from(sessions.values()), [sessions]);

  return (
    <Instances limit={200}>
      <sphereGeometry args={[1, 16, 16]} />
      <meshStandardMaterial
        emissive="white"
        emissiveIntensity={0.5}
        roughness={0.3}
        metalness={0.5}
        toneMapped={false}
      />
      {sessionArray.map((s, i) => (
        <SessionNode
          key={s.session_id}
          data={s}
          index={i}
          total={sessionArray.length}
          onClick={onSelect}
          selected={selectedId === s.session_id}
        />
      ))}
    </Instances>
  );
}
