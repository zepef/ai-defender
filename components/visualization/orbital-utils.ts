import * as THREE from "three";

export const ORBIT_SPEED = 0.1;
export const VERTICAL_SPEED = 0.5;
export const VERTICAL_AMPLITUDE = 0.3;

export const ESCALATION_RADIUS: Record<number, number> = {
  0: 10,
  1: 8,
  2: 6,
  3: 4,
};

export interface VividColorConfig {
  color: string;
  emissive: string;
  emissiveIntensity: number;
  roughness: number;
}

export const VIVID_COLORS: Record<number, VividColorConfig> = {
  0: { color: "#4ade80", emissive: "#22c55e", emissiveIntensity: 0.3, roughness: 0.5 },
  1: { color: "#facc15", emissive: "#eab308", emissiveIntensity: 0.6, roughness: 0.4 },
  2: { color: "#fb923c", emissive: "#f97316", emissiveIntensity: 1.2, roughness: 0.2 },
  3: { color: "#ff2020", emissive: "#ff0000", emissiveIntensity: 2.5, roughness: 0.1 },
};

export function hashCode(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0;
  }
  return Math.abs(hash);
}

const _tempVec = new THREE.Vector3();

export function computeSessionPosition(
  sessionId: string,
  escalationLevel: number,
  index: number,
  elapsedTime: number,
  out?: THREE.Vector3,
): THREE.Vector3 {
  const target = out ?? _tempVec;
  const angle = (hashCode(sessionId) % 1000) / 1000 * Math.PI * 2;
  const radius = ESCALATION_RADIUS[escalationLevel] ?? 10;
  const currentAngle = angle + elapsedTime * ORBIT_SPEED;
  const x = Math.cos(currentAngle) * radius;
  const z = Math.sin(currentAngle) * radius;
  const y = Math.sin(elapsedTime * VERTICAL_SPEED + index) * VERTICAL_AMPLITUDE;
  target.set(x, y, z);
  return target;
}
