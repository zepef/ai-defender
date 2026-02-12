"use client";

import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import type { SessionNodeData } from "./session-nodes";
import { computeSessionPosition, VIVID_COLORS } from "./orbital-utils";
import * as THREE from "three";

function Edge({ data, index }: { data: SessionNodeData; index: number }) {
  const lineRef = useRef<THREE.Line>(null);
  const posVec = useMemo(() => new THREE.Vector3(), []);
  const color = (VIVID_COLORS[data.escalation_level] ?? VIVID_COLORS[0]).color;

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array(6); // 2 points x 3 components
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    return geo;
  }, []);

  const material = useMemo(
    () =>
      new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity: 0.15,
      }),
    [color],
  );

  useFrame(({ clock }) => {
    computeSessionPosition(
      data.session_id,
      data.escalation_level,
      index,
      clock.getElapsedTime(),
      posVec,
    );
    const posAttr = geometry.getAttribute("position") as THREE.BufferAttribute;
    // Point 0: origin (honeypot core)
    posAttr.setXYZ(0, 0, 0, 0);
    // Point 1: session node position
    posAttr.setXYZ(1, posVec.x, posVec.y, posVec.z);
    posAttr.needsUpdate = true;
  });

  return <primitive ref={lineRef} object={new THREE.Line(geometry, material)} />;
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
