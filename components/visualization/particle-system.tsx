"use client";

import { useRef, useMemo, useCallback } from "react";
import { useFrame } from "@react-three/fiber";
import { Instance, Instances } from "@react-three/drei";
import * as THREE from "three";

const POOL_SIZE = 100;
const PARTICLE_DURATION = 1.2; // seconds

const TOOL_COLORS: Record<string, string> = {
  nmap_scan: "#3b82f6",    // blue
  file_read: "#a855f7",    // purple
  shell_exec: "#f59e0b",   // amber
  sqlmap: "#ef4444",        // red
  browser_navigate: "#06b6d4", // cyan
};

interface ParticleData {
  active: boolean;
  startTime: number;
  from: THREE.Vector3;
  to: THREE.Vector3;
  color: string;
}

export interface ParticleSystemHandle {
  spawn: (fromPos: THREE.Vector3, toolName: string) => void;
}

function Particle({ data, clock }: { data: ParticleData; clock: THREE.Clock }) {
  const ref = useRef<THREE.InstancedMesh>(null);

  useFrame(() => {
    if (!ref.current || !data.active) {
      if (ref.current) ref.current.scale.setScalar(0);
      return;
    }

    const elapsed = clock.getElapsedTime() - data.startTime;
    const progress = Math.min(elapsed / PARTICLE_DURATION, 1);

    if (progress >= 1) {
      data.active = false;
      ref.current.scale.setScalar(0);
      return;
    }

    // Lerp position from session to core with slight arc
    const x = data.from.x + (data.to.x - data.from.x) * progress;
    const z = data.from.z + (data.to.z - data.from.z) * progress;
    const arcHeight = Math.sin(progress * Math.PI) * 2;
    const y = data.from.y + (data.to.y - data.from.y) * progress + arcHeight;

    ref.current.position.set(x, y, z);

    // Scale: grow then shrink
    const scale = Math.sin(progress * Math.PI) * 0.2;
    ref.current.scale.setScalar(scale);
  });

  return (
    <Instance
      ref={ref}
      scale={0}
      color={data.color}
    />
  );
}

export function ParticleSystem({
  onReady,
}: {
  onReady: (handle: ParticleSystemHandle) => void;
}) {
  const particles = useRef<ParticleData[]>(
    Array.from({ length: POOL_SIZE }, () => ({
      active: false,
      startTime: 0,
      from: new THREE.Vector3(),
      to: new THREE.Vector3(0, 0, 0),
      color: "#ffffff",
    }))
  );

  const nextIndex = useRef(0);
  const clockRef = useRef<THREE.Clock | null>(null);

  useFrame(({ clock }) => {
    clockRef.current = clock;
  });

  const spawn = useCallback(
    (fromPos: THREE.Vector3, toolName: string) => {
      if (!clockRef.current) return;
      const idx = nextIndex.current % POOL_SIZE;
      nextIndex.current += 1;

      const p = particles.current[idx];
      p.active = true;
      p.startTime = clockRef.current.getElapsedTime();
      p.from.copy(fromPos);
      p.to.set(0, 0, 0);
      p.color = TOOL_COLORS[toolName] ?? "#ffffff";
    },
    []
  );

  const handle = useMemo(() => ({ spawn }), [spawn]);

  // Notify parent of handle once
  const readyRef = useRef(false);
  useFrame(() => {
    if (!readyRef.current && clockRef.current) {
      readyRef.current = true;
      onReady(handle);
    }
  });

  return (
    <Instances limit={POOL_SIZE}>
      <sphereGeometry args={[1, 8, 8]} />
      <meshBasicMaterial toneMapped={false} />
      {particles.current.map((p, i) => (
        <Particle key={i} data={p} clock={clockRef.current || new THREE.Clock()} />
      ))}
    </Instances>
  );
}
