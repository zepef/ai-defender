"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Instance, Instances } from "@react-three/drei";
import * as THREE from "three";
import { computeSessionPosition, VIVID_COLORS, type VividColorConfig } from "./orbital-utils";

export interface SessionNodeData {
  session_id: string;
  escalation_level: number;
  interaction_count: number;
  client_info: Record<string, string>;
  timestamp: string;
}

function SessionNode({
  data,
  index,
  onClick,
  selected,
}: {
  data: SessionNodeData;
  index: number;
  onClick: (id: string) => void;
  selected: boolean;
}) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const posVec = useMemo(() => new THREE.Vector3(), []);

  const color = (VIVID_COLORS[data.escalation_level] ?? VIVID_COLORS[0]).color;
  const size = Math.min(0.3 + data.interaction_count * 0.05, 0.8);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    computeSessionPosition(
      data.session_id,
      data.escalation_level,
      index,
      clock.getElapsedTime(),
      posVec,
    );
    ref.current.position.copy(posVec);
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

function SessionLevelGroup({
  level,
  sessions,
  selectedId,
  onSelect,
  indexMap,
}: {
  level: number;
  sessions: SessionNodeData[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  indexMap: Map<string, number>;
}) {
  const cfg: VividColorConfig = VIVID_COLORS[level] ?? VIVID_COLORS[0];

  return (
    <Instances limit={200}>
      <sphereGeometry args={[1, 16, 16]} />
      <meshStandardMaterial
        color={cfg.color}
        emissive={cfg.emissive}
        emissiveIntensity={cfg.emissiveIntensity}
        roughness={cfg.roughness}
        metalness={0.5}
        toneMapped={false}
      />
      {sessions.map((s) => (
        <SessionNode
          key={s.session_id}
          data={s}
          index={indexMap.get(s.session_id) ?? 0}
          onClick={onSelect}
          selected={selectedId === s.session_id}
        />
      ))}
    </Instances>
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
  const { groups, indexMap } = useMemo(() => {
    const grouped = new Map<number, SessionNodeData[]>();
    const idxMap = new Map<string, number>();
    let i = 0;
    for (const s of sessions.values()) {
      const level = s.escalation_level;
      if (!grouped.has(level)) grouped.set(level, []);
      grouped.get(level)!.push(s);
      idxMap.set(s.session_id, i++);
    }
    return { groups: grouped, indexMap: idxMap };
  }, [sessions]);

  return (
    <group>
      {Array.from(groups.entries()).map(([level, levelSessions]) => (
        <SessionLevelGroup
          key={level}
          level={level}
          sessions={levelSessions}
          selectedId={selectedId}
          onSelect={onSelect}
          indexMap={indexMap}
        />
      ))}
    </group>
  );
}
