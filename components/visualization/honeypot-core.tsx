"use client";

import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Sphere, MeshDistortMaterial } from "@react-three/drei";
import type { Mesh } from "three";

export function HoneypotCore() {
  const meshRef = useRef<Mesh>(null);

  useFrame(({ clock }) => {
    if (meshRef.current) {
      const t = clock.getElapsedTime();
      const scale = 1 + Math.sin(t * 0.8) * 0.05;
      meshRef.current.scale.setScalar(scale);
    }
  });

  return (
    <group>
      {/* Core sphere */}
      <Sphere ref={meshRef} args={[1.5, 64, 64]}>
        <MeshDistortMaterial
          color="#4488ff"
          emissive="#4488ff"
          emissiveIntensity={0.8}
          roughness={0.2}
          metalness={0.8}
          distort={0.3}
          speed={1.5}
        />
      </Sphere>

      {/* Outer glow shell */}
      <Sphere args={[2.0, 32, 32]}>
        <meshBasicMaterial
          color="#4488ff"
          transparent
          opacity={0.08}
        />
      </Sphere>

      {/* Inner ring */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[2.2, 0.02, 16, 64]} />
        <meshBasicMaterial color="#6699ff" transparent opacity={0.3} />
      </mesh>
    </group>
  );
}
