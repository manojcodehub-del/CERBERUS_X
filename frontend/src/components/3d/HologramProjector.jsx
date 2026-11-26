import { useFrame } from '@react-three/fiber'
import { useRef } from 'react'
import { useReducedMotion } from 'framer-motion'

export default function HologramProjector() {
  const assembly = useRef()
  const reduced = useReducedMotion()
  useFrame((_, delta) => {
    if (assembly.current && !reduced) assembly.current.rotation.y += delta * 0.07
  })

  return <group position={[0, -0.9, 0]}>
    <mesh position={[0, -0.08, 0]}>
      <cylinderGeometry args={[0.7, 0.85, 0.16, 48]} />
      <meshStandardMaterial color="#122940" metalness={0.76} roughness={0.3} />
    </mesh>
    <mesh position={[0, -0.17, 0]}>
      <cylinderGeometry args={[0.88, 0.94, 0.07, 48]} />
      <meshStandardMaterial color="#0c1729" metalness={0.68} roughness={0.32} />
    </mesh>
    <mesh position={[0, 0.015, 0]} rotation={[Math.PI / 2, 0, 0]}>
      <torusGeometry args={[0.57, 0.012, 8, 72]} />
      <meshBasicMaterial color="#00c8ff" transparent opacity={0.83} />
    </mesh>
    <mesh position={[0, 0.11, 0]} rotation={[Math.PI / 2, 0, 0]}>
      <torusGeometry args={[0.36, 0.009, 8, 72]} />
      <meshBasicMaterial color="#8b5cf6" transparent opacity={0.7} />
    </mesh>
    <group ref={assembly}>
      <mesh position={[0, 0.65, 0]}>
        <coneGeometry args={[0.63, 1.18, 32, 1, true]} />
        <meshBasicMaterial color="#00c8ff" transparent opacity={0.045} depthWrite={false} side={2} />
      </mesh>
      <mesh position={[0, 1.26, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.53, 0.008, 6, 64]} />
        <meshBasicMaterial color="#00c8ff" transparent opacity={0.44} />
      </mesh>
      <mesh position={[0, 1.55, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.31, 0.006, 6, 64]} />
        <meshBasicMaterial color="#8b5cf6" transparent opacity={0.46} />
      </mesh>
    </group>
    <pointLight color="#00c8ff" intensity={0.9} distance={2.2} position={[0, 0.1, 0]} />
  </group>
}
