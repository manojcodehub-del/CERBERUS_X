import { Canvas, useFrame } from '@react-three/fiber'
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
      <torusGeometry args={[radius, 0.012, 8, 112]} />
      <meshBasicMaterial color={color} transparent opacity={0.78} />
    </mesh>
    {marker && <>
      <mesh position={[radius, 0, 0]}>
        <sphereGeometry args={[0.035, 12, 12]} />
        <meshBasicMaterial color={color} />
      </mesh>
      <mesh position={[-radius, 0, 0]}>
        <sphereGeometry args={[0.018, 8, 8]} />
        <meshBasicMaterial color={color} transparent opacity={0.62} />
      </mesh>
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

function CoreModel() {
  const sphere = useRef()
  const root = useRef()
  const satellites = useRef()
  const reduced = useReducedMotion()
  const particlePositions = useMemo(() => Array.from({ length: 44 }, (_, index) => {
    const angle = index * 2.399
    const radius = 1.28 + (index % 6) * 0.105
    const height = ((index % 9) - 4) * 0.13
    return [Math.cos(angle) * radius, height, Math.sin(angle) * radius]
  }), [])

  useFrame((state, delta) => {
    if (root.current && !reduced) {
      root.current.rotation.x += (state.pointer.y * 0.075 - root.current.rotation.x) * delta * 1.4
      root.current.rotation.z += (-state.pointer.x * 0.075 - root.current.rotation.z) * delta * 1.4
    }
    if (sphere.current && !reduced) {
      sphere.current.rotation.y += delta * 0.16
      sphere.current.rotation.x += delta * 0.045
      sphere.current.position.y = Math.sin(state.clock.elapsedTime * 0.62) * 0.055
      const pulse = 1 + Math.sin(state.clock.elapsedTime * 0.8) * 0.018
      sphere.current.scale.setScalar(pulse)
    }
    if (satellites.current && !reduced) satellites.current.rotation.y -= delta * 0.025
  })

  return <group ref={root}>
    <ambientLight intensity={0.55} />
    <pointLight color="#00c8ff" intensity={2.2} distance={5} position={[1.4, 1.1, 1.5]} />
    <pointLight color="#4a54e8" intensity={1.1} distance={4} position={[-1.4, -0.5, -1.1]} />
    <PulseHalo reduced={reduced} />
    <mesh ref={sphere}>
      <icosahedronGeometry args={[0.56, 2]} />
      <meshStandardMaterial color="#0a3658" emissive="#006d9b" emissiveIntensity={0.8} metalness={0.55} roughness={0.26} />
    </mesh>
    <mesh>
      <icosahedronGeometry args={[0.595, 2]} />
      <meshBasicMaterial color="#69e6ff" wireframe transparent opacity={0.7} />
    </mesh>
    <mesh rotation={[0.2, 0.25, 0]}>
      <sphereGeometry args={[0.64, 18, 18]} />
      <meshBasicMaterial color="#38c9ff" wireframe transparent opacity={0.12} />
    </mesh>
    <OrbitalRing radius={0.79} rotation={[0.55, 0.26, 0.1]} speed={0.19} color="#00c8ff" reduced={reduced} />
    <OrbitalRing radius={1.02} rotation={[1.15, 0.4, 0.48]} speed={-0.13} color="#2563eb" reduced={reduced} />
    <OrbitalRing radius={1.22} rotation={[0.9, 1.05, -0.35]} speed={0.085} color="#8b5cf6" reduced={reduced} marker={false} />
    <group ref={satellites}>
      {particlePositions.map((position, index) => <mesh key={index} position={position}>
        <sphereGeometry args={[index % 5 === 0 ? 0.022 : 0.012, 7, 7]} />
        <meshBasicMaterial color={index % 7 === 0 ? '#b69cff' : '#82eaff'} transparent opacity={index % 5 === 0 ? 0.82 : 0.5} />
      </mesh>)}
    </group>
    <Sparkles count={16} scale={3.05} size={1.25} speed={reduced ? 0 : 0.18} color="#b3f2ff" />
  </group>
}

export function AIOrb() {
  return <div className="orb-stage" aria-label="Decorative local 3D AI core">
    <Canvas dpr={[1, 1.2]} camera={{ position: [0, 0, 3.65], fov: 42 }} gl={{ antialias: false, alpha: true, powerPreference: 'low-power' }} fallback={<div className="orb-fallback"><div className="fallback-core" /></div>}>
      <CoreModel />
    </Canvas>
    <div className="orb-caption"><span className="orb-live" /> LOCAL INTELLIGENCE CORE</div>
  </div>
}
