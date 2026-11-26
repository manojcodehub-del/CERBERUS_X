import { Canvas, useFrame } from '@react-three/fiber'
import { Html, Line, OrbitControls } from '@react-three/drei'
import { useMemo, useRef } from 'react'
import { AdditiveBlending } from 'three'
import { useReducedMotion } from 'framer-motion'

const nodeColor = (type = '') => ({ document: '#2563eb', claim: '#00c8ff', evidence: '#16a34a', event: '#f59e0b', conflict: '#ef4444', entity: '#8b5cf6' }[type.toLowerCase()] || '#8b5cf6')

function positionsFor(nodes) {
  const golden = Math.PI * (3 - Math.sqrt(5))
  return new Map(nodes.map((node, index) => {
    const y = 1 - (index / Math.max(1, nodes.length - 1)) * 2
    const radius = Math.sqrt(Math.max(0, 1 - y * y))
    const angle = golden * index
    const layer = index % 3
    return [node.id, [Math.cos(angle) * radius * 2.15, y * 1.55, Math.sin(angle) * radius * 2.15 + (layer - 1) * 0.12]]
  }))
}

function GraphNode({ node, position, selected, onSelect }) {
  const aura = useRef()
  const reduced = useReducedMotion()
  const phaseOffset = useMemo(() => [...String(node.id)].reduce((sum, character) => sum + character.charCodeAt(0), 0) * 0.01, [node.id])
  useFrame((state) => {
    if (!aura.current) return
    const pulse = reduced ? 1 : 0.94 + (Math.sin(state.clock.elapsedTime * 1.5 + phaseOffset) + 1) * 0.035
    aura.current.scale.setScalar(pulse)
  })
  return <group position={position}>
    <mesh onClick={(event) => { event.stopPropagation(); onSelect(node) }}>
      <sphereGeometry args={[selected ? 0.082 : 0.06, 16, 16]} />
      <meshStandardMaterial color={nodeColor(node.type)} emissive={nodeColor(node.type)} emissiveIntensity={selected ? 1.1 : 0.55} metalness={0.32} roughness={0.3} />
    </mesh>
    <mesh ref={aura}>
      <sphereGeometry args={[selected ? 0.14 : 0.12, 12, 12]} />
      <meshBasicMaterial color={nodeColor(node.type)} transparent opacity={selected ? 0.17 : 0.09} blending={AdditiveBlending} depthWrite={false} />
    </mesh>
    <Html center distanceFactor={10} zIndexRange={[40, 0]}>
      <button className={`graph-node-hit ${selected ? 'selected' : ''}`} style={{ '--node-color': nodeColor(node.type) }} aria-label={`Select ${node.label}`} title={node.label} onClick={(event) => { event.stopPropagation(); onSelect(node) }} />
    </Html>
    {selected && <mesh>
      <ringGeometry args={[0.105, 0.126, 24]} />
      <meshBasicMaterial color="#a6efff" side={2} />
    </mesh>}
  </group>
}

function EdgeEnergy({ start, end, index, reduced, color }) {
  const ref = useRef()
  useFrame((state) => {
    if (!ref.current) return
    const progress = reduced ? ((index % 5) + 1) / 6 : (state.clock.elapsedTime * 0.13 + index * 0.173) % 1
    ref.current.position.set(
      start[0] + (end[0] - start[0]) * progress,
      start[1] + (end[1] - start[1]) * progress,
      start[2] + (end[2] - start[2]) * progress,
    )
  })
  return <mesh ref={ref}>
    <sphereGeometry args={[0.024, 8, 8]} />
    <meshBasicMaterial color={color} toneMapped={false} />
  </mesh>
}

export default function KnowledgeGraph3D({ nodes, edges, selectedId, onSelect, controlsRef }) {
  const positions = useMemo(() => positionsFor(nodes), [nodes])
  const validEdges = edges.filter((edge) => positions.has(edge.source) && positions.has(edge.target))
  const reduced = useReducedMotion()
  const activeEdges = validEdges.slice(0, 36)
  return <div className="graph-canvas graph-canvas-3d">
    <Canvas dpr={[1, 1.25]} camera={{ position: [0, 0, 7.7], fov: 47 }} gl={{ antialias: false, alpha: true, powerPreference: 'low-power' }} fallback={<div className="graph-fallback-message">3D rendering is unavailable. Switch to the 2D evidence graph.</div>}>
      <color attach="background" args={['#080d18']} />
      {validEdges.map((edge) => <Line key={`e-${edge.id}`} points={[positions.get(edge.source), positions.get(edge.target)]} color={edge.relationship?.includes('CONFLICT') ? '#ef4444' : '#28719a'} transparent opacity={0.36} lineWidth={0.8} />)}
      {activeEdges.map((edge, index) => <EdgeEnergy key={`energy-${edge.id}`} start={positions.get(edge.source)} end={positions.get(edge.target)} index={index} reduced={reduced} color={edge.relationship?.includes('CONFLICT') ? '#ff7e7e' : '#7be7ff'} />)}
      {nodes.map((node) => <GraphNode key={node.id} node={node} position={positions.get(node.id)} selected={node.id === selectedId} onSelect={onSelect} />)}
      <OrbitControls ref={controlsRef} enableDamping={!reduced} dampingFactor={0.09} minDistance={3} maxDistance={14} />
    </Canvas>
    <div className="graph-controls-hint">Drag to rotate · right-drag to pan · scroll to zoom</div>
  </div>
}
