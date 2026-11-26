import { useFrame } from '@react-three/fiber'
import { Sparkles } from '@react-three/drei'
import { AdditiveBlending } from 'three'
import { useMemo, useRef } from 'react'
import { useReducedMotion } from 'framer-motion'

function OrbitalRing({ radius, rotation, speed, color, reduced, marker = true }) {
  const ref = useRef()
  useFrame((_, delta) => {
    if (ref.current && !reduced) ref.current.rotation.z += delta * speed
  })

  return <group ref={ref} rotation={rotation}>
    <mesh>
      <torusGeometry args={[radius, 0.012, 8, 96]} />
      <meshBasicMaterial color={color} transparent opacity={0.76} />
    </mesh>
    {marker && <>
      <mesh position={[radius, 0, 0]}><sphereGeometry args={[0.032, 10, 10]} /><meshBasicMaterial color={color} /></mesh>
      <mesh position={[-radius, 0, 0]}><sphereGeometry args={[0.017, 8, 8]} /><meshBasicMaterial color={color} transparent opacity={0.62} /></mesh>
    </>}
  </group>
}

function PulseHalo({ reduced }) {
  const halo = useRef()
  useFrame((state) => {
    if (!halo.current || reduced) return
    const pulse = (Math.sin(state.clock.elapsedTime * 0.7) + 1) / 2
    halo.current.scale.setScalar(0.92 + pulse * 0.1)
    halo.current.material.opacity = 0.045 + pulse * 0.035
  })
  return <mesh ref={halo}>
    <sphereGeometry args={[0.82, 24, 24]} />
    <meshBasicMaterial color="#00c8ff" transparent opacity={0.06} blending={AdditiveBlending} depthWrite={false} />
  </mesh>
}

export default function HologramCore() {
  const sphere = useRef()
  const root = useRef()
  const satellites = useRef()
  const reduced = useReducedMotion()
  const particlePositions = useMemo(() => Array.from({ length: 42 }, (_, index) => {
    const angle = index * 2.399
    const radius = 1.25 + (index % 6) * 0.1
    const height = ((index % 9) - 4) * 0.12
    return [Math.cos(angle) * radius, height, Math.sin(angle) * radius]
  }), [])

  useFrame((state, delta) => {
    if (root.current && !reduced) {
      root.current.rotation.x += (state.pointer.y * 0.06 - root.current.rotation.x) * delta * 1.3
      root.current.rotation.z += (-state.pointer.x * 0.06 - root.current.rotation.z) * delta * 1.3
    }
    if (sphere.current && !reduced) {
      sphere.current.rotation.y += delta * 0.14
      sphere.current.rotation.x += delta * 0.04
      sphere.current.position.y = Math.sin(state.clock.elapsedTime * 0.6) * 0.045
      sphere.current.scale.setScalar(1 + Math.sin(state.clock.elapsedTime * 0.8) * 0.016)
    }
    if (satellites.current && !reduced) satellites.current.rotation.y -= delta * 0.022
  })

  return <group ref={root} position={[0, 0.42, 0]}>
    <ambientLight intensity={0.55} />
    <pointLight color="#00c8ff" intensity={1.8} distance={5} position={[1.4, 1.1, 1.5]} />
    <pointLight color="#4a54e8" intensity={0.9} distance={4} position={[-1.4, -0.5, -1.1]} />
    <PulseHalo reduced={reduced} />
    <mesh ref={sphere}>
      <icosahedronGeometry args={[0.54, 2]} />
      <meshStandardMaterial color="#0a3658" emissive="#006d9b" emissiveIntensity={0.8} metalness={0.55} roughness={0.26} />
    </mesh>
    <mesh><icosahedronGeometry args={[0.575, 2]} /><meshBasicMaterial color="#69e6ff" wireframe transparent opacity={0.7} /></mesh>
    <mesh rotation={[0.2, 0.25, 0]}><sphereGeometry args={[0.62, 18, 18]} /><meshBasicMaterial color="#38c9ff" wireframe transparent opacity={0.12} /></mesh>
    <OrbitalRing radius={0.76} rotation={[0.55, 0.26, 0.1]} speed={0.17} color="#00c8ff" reduced={reduced} />
    <OrbitalRing radius={0.97} rotation={[1.15, 0.4, 0.48]} speed={-0.12} color="#2563eb" reduced={reduced} />
    <OrbitalRing radius={1.16} rotation={[0.9, 1.05, -0.35]} speed={0.08} color="#8b5cf6" reduced={reduced} marker={false} />
    <group ref={satellites}>
      {particlePositions.map((position, index) => <mesh key={index} position={position}>
        <sphereGeometry args={[index % 5 === 0 ? 0.02 : 0.011, 7, 7]} />
        <meshBasicMaterial color={index % 7 === 0 ? '#b69cff' : '#82eaff'} transparent opacity={index % 5 === 0 ? 0.78 : 0.46} />
      </mesh>)}
    </group>
    <Sparkles count={14} scale={2.9} size={1.1} speed={reduced ? 0 : 0.16} color="#b3f2ff" />
  </group>
}
