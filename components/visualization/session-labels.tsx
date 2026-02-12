"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Billboard, Text } from "@react-three/drei";
import * as THREE from "three";
import type { SessionNodeData } from "./session-nodes";
import { computeSessionPosition, VIVID_COLORS } from "./orbital-utils";

const MAX_VISIBLE_LABELS = 30;
const LABEL_Y_OFFSET = 0.6;

function SessionLabel({
  data,
  index,
  selected,
}: {
  data: SessionNodeData;
  index: number;
  selected: boolean;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const posVec = useMemo(() => new THREE.Vector3(), []);

  const label = useMemo(() => {
    const name = data.client_info?.name || "Unknown";
    const prefix = data.session_id.slice(0, 6);
    return `${name}\n${prefix}`;
  }, [data.client_info, data.session_id]);

  const colorConfig = VIVID_COLORS[data.escalation_level] ?? VIVID_COLORS[0];

  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    computeSessionPosition(
      data.session_id,
      data.escalation_level,
      index,
      clock.getElapsedTime(),
      posVec,
    );
    groupRef.current.position.set(posVec.x, posVec.y + LABEL_Y_OFFSET, posVec.z);
  });

  return (
    <group ref={groupRef}>
      <Billboard follow lockX={false} lockY={false} lockZ={false}>
        <Text
          fontSize={selected ? 0.35 : 0.22}
          color={colorConfig.color}
          anchorX="center"
          anchorY="bottom"
          textAlign="center"
          fillOpacity={selected ? 1 : 0.7}
          outlineWidth={0.02}
          outlineColor="#000000"
        >
          {label}
        </Text>
      </Billboard>
    </group>
  );
}

export function SessionLabels({
  sessions,
  selectedId,
}: {
  sessions: Map<string, SessionNodeData>;
  selectedId: string | null;
}) {
  const visible = useMemo(() => {
    const all = Array.from(sessions.values());

    // Sort by escalation (desc) then recency (desc)
    all.sort((a, b) => {
      if (b.escalation_level !== a.escalation_level) {
        return b.escalation_level - a.escalation_level;
      }
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
    });

    const result: SessionNodeData[] = [];
    let selectedNode: SessionNodeData | null = null;

    for (const s of all) {
      if (s.session_id === selectedId) {
        selectedNode = s;
        continue;
      }
      if (result.length < MAX_VISIBLE_LABELS - (selectedId ? 1 : 0)) {
        result.push(s);
      }
    }

    // Selected always included
    if (selectedNode) {
      result.unshift(selectedNode);
    }

    return result;
  }, [sessions, selectedId]);

  // Build a stable index map from the full sessions list for orbital position consistency
  const indexMap = useMemo(() => {
    const map = new Map<string, number>();
    let i = 0;
    for (const [id] of sessions) {
      map.set(id, i++);
    }
    return map;
  }, [sessions]);

  return (
    <group>
      {visible.map((s) => (
        <SessionLabel
          key={s.session_id}
          data={s}
          index={indexMap.get(s.session_id) ?? 0}
          selected={s.session_id === selectedId}
        />
      ))}
    </group>
  );
}
