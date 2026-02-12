"use client";

import { useMemo, useEffect } from "react";
import { useFrame } from "@react-three/fiber";
import type { SessionNodeData } from "./session-nodes";
import { computeSessionPosition, VIVID_COLORS } from "./orbital-utils";
import * as THREE from "three";

function Edge({ data, index }: { data: SessionNodeData; index: number }) {
  const posVec = useMemo(() => new THREE.Vector3(), []);

  const lineObj = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array(6);
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const mat = new THREE.LineBasicMaterial({
      transparent: true,
      opacity: 0.15,
    });
    return new THREE.Line(geo, mat);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update color when escalation changes without recreating the object
  useEffect(() => {
    const color = (VIVID_COLORS[data.escalation_level] ?? VIVID_COLORS[0]).color;
    (lineObj.material as THREE.LineBasicMaterial).color.set(color);
  }, [data.escalation_level, lineObj]);

  useFrame(({ clock }) => {
    computeSessionPosition(
      data.session_id,
      data.escalation_level,
      index,
      clock.getElapsedTime(),
      posVec,
    );
    const posAttr = lineObj.geometry.getAttribute("position") as THREE.BufferAttribute;
    posAttr.setXYZ(0, 0, 0, 0);
    posAttr.setXYZ(1, posVec.x, posVec.y, posVec.z);
    posAttr.needsUpdate = true;
  });

  return <primitive object={lineObj} />;
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
