"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import type { SessionNodeData } from "./session-nodes";
import { computeSessionPosition, VIVID_COLORS } from "./orbital-utils";
import * as THREE from "three";

function Edge({ data, index }: { data: SessionNodeData; index: number }) {
  const ref = useRef<THREE.Group>(null);
  const posVec = useMemo(() => new THREE.Vector3(), []);
  const color = (VIVID_COLORS[data.escalation_level] ?? VIVID_COLORS[0]).color;

  const pointsRef = useRef<[number, number, number][]>([
    [0, 0, 0],
    [10, 0, 0],
  ]);

  useFrame(({ clock }) => {
    computeSessionPosition(
      data.session_id,
      data.escalation_level,
      index,
      clock.getElapsedTime(),
      posVec,
    );
    pointsRef.current = [
      [0, 0, 0],
      [posVec.x, posVec.y, posVec.z],
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
