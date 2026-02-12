"use client";

import { OrbitControls, Stars, Grid } from "@react-three/drei";
import { EffectComposer, Bloom, Vignette } from "@react-three/postprocessing";

export function SceneSetup() {
  return (
    <>
      <ambientLight intensity={0.15} />
      <pointLight position={[0, 10, 0]} intensity={0.5} color="#4488ff" />
      <pointLight position={[10, 5, -10]} intensity={0.3} color="#8844ff" />

      <OrbitControls
        makeDefault
        enablePan={false}
        minDistance={8}
        maxDistance={40}
        maxPolarAngle={Math.PI / 2 + 0.3}
      />

      <Stars radius={80} depth={60} count={2000} factor={3} fade speed={0.5} />

      <Grid
        position={[0, -2, 0]}
        args={[60, 60]}
        cellSize={1}
        cellThickness={0.3}
        cellColor="#1a1a2e"
        sectionSize={5}
        sectionThickness={0.6}
        sectionColor="#2a2a4e"
        fadeDistance={40}
        infiniteGrid
      />

      <EffectComposer>
        <Bloom
          luminanceThreshold={0.2}
          luminanceSmoothing={0.9}
          intensity={1.5}
        />
        <Vignette darkness={0.5} offset={0.3} />
      </EffectComposer>
    </>
  );
}
