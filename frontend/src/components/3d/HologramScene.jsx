import { Canvas } from '@react-three/fiber'
import { Clone, Sparkles, useGLTF } from '@react-three/drei'
import { Component, Suspense, useEffect, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import { useReducedMotion } from 'framer-motion'
import HologramCore from './HologramCore'
import HologramProjector from './HologramProjector'

const PROJECTOR_MODEL = '/models/hologram-projector.glb'

function LocalProjectorAsset() {
  const group = useRef()
  const reduced = useReducedMotion()
  const { scene } = useGLTF(PROJECTOR_MODEL)
  useFrame((_, delta) => {
    if (group.current && !reduced) group.current.rotation.y += delta * 0.07
  })
  return <group ref={group} position={[0, -1.1, 0]}><Clone object={scene} scale={0.9} /></group>
}

class ProjectorAssetBoundary extends Component {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? <HologramProjector /> : this.props.children }
}

export default function HologramScene() {
  const [localModelAvailable, setLocalModelAvailable] = useState(false)
  const reduced = useReducedMotion()

  useEffect(() => {
    const controller = new AbortController()
    fetch(PROJECTOR_MODEL, { method: 'HEAD', signal: controller.signal })
      .then((response) => {
        const type = response.headers.get('content-type') || ''
        setLocalModelAvailable(response.ok && !type.toLowerCase().includes('text/html'))
      })
      .catch(() => setLocalModelAvailable(false))
    return () => controller.abort()
  }, [])

  return <div className="orb-stage hologram-scene" aria-label="Decorative 3D holographic intelligence core and projector">
    <Canvas dpr={[1, 1.15]} camera={{ position: [0, 0.2, 5.15], fov: 42 }} gl={{ antialias: false, alpha: true, powerPreference: 'low-power' }} fallback={<div className="orb-fallback"><div className="fallback-core" /></div>}>
      <Suspense fallback={null}>
        <ambientLight intensity={0.35} />
        <HologramCore />
        <ProjectorAssetBoundary key={localModelAvailable ? 'asset' : 'procedural'}>
          {localModelAvailable ? <Suspense fallback={<HologramProjector />}><LocalProjectorAsset /></Suspense> : <HologramProjector />}
        </ProjectorAssetBoundary>
        <Sparkles count={28} scale={[3.2, 3.6, 2.5]} size={1.15} speed={reduced ? 0 : 0.11} color="#5bdcff" />
      </Suspense>
    </Canvas>
    <div className="orb-caption"><span className="orb-live" /> LOCAL INTELLIGENCE CORE</div>
  </div>
}
