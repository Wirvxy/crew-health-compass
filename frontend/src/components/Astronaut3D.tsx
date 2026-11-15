import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { AstronautHealth, HEALTH_COLORS, healthZones } from './astronautHealth'
import type { HealthSignal } from './astronautHealth'
import type { CSSProperties } from 'react'
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js'

// "astronaut" by Antropik on Sketchfab, CC BY 4.0 (see public/licenses/Astronaut-model-NOTICE.txt).
// The FBX and its textures are served by this app, so nothing is fetched from Sketchfab at runtime.
const MODEL_URL = `${import.meta.env.BASE_URL}models/astronaut/astronaut.fbx`
const MODEL_SOURCE = 'https://sketchfab.com/3d-models/astronaut-482bf87662fd4b378bcb3a2931d59ca3'
const LICENSE_URL = 'https://creativecommons.org/licenses/by/4.0/'
const FIT_HEIGHT = 2.6

type Status = 'loading' | 'ready' | 'error'
interface Stage { camera: THREE.PerspectiveCamera; pivot: THREE.Group; health: AstronautHealth | null; render: () => void }
function disposeTree(root: THREE.Object3D) {
  root.traverse(object => {
    const mesh = object as THREE.Mesh
    mesh.geometry?.dispose()
    const materials = Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : []
    for (const material of materials) {
      for (const value of Object.values(material)) if (value instanceof THREE.Texture) value.dispose()
      material.dispose()
    }
  })
}

export default function Astronaut3D({ signals, selected, onSelect }: { signals: HealthSignal[]; selected: string | null; onSelect: (id: string) => void }) {
  const zones = useMemo(() => healthZones(signals), [signals])
  const zonesRef = useRef(zones)
  zonesRef.current = zones
  const boxes = useRef(new Map<string, HTMLDivElement>())
  const lines = useRef(new Map<string, SVGPolylineElement>())
  const canvas = useRef<HTMLCanvasElement>(null), drag = useRef<{ x: number; y: number } | null>(null), stage = useRef<Stage | null>(null)
  const press = useRef<{ x: number; y: number } | null>(null)
  const [angle, setAngle] = useState(-.3), [pitch, setPitch] = useState(0), [zoom, setZoom] = useState(1)
  const [status, setStatus] = useState<Status>('loading'), [problem, setProblem] = useState('')

  useEffect(() => {
    const el = canvas.current
    if (!el) return
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ canvas: el, antialias: true, alpha: true })
    } catch {
      setStatus('error'); setProblem('This browser cannot show the 3D view (WebGL is unavailable).')
      return
    }
    let disposed = false
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(30, 1, .01, 100)
    camera.position.set(0, 0, 6.2)
    scene.add(new THREE.HemisphereLight(0xdfefff, 0x203040, 1.6))
    const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(2, 3, 4); scene.add(key)
    const rim = new THREE.DirectionalLight(0x8be3d0, .8); rim.position.set(-3, 1, -2); scene.add(rim)
    const pivot = new THREE.Group(); scene.add(pivot)
    const render = () => {
      scene.updateMatrixWorld(true)
      camera.updateMatrixWorld(true)
      stage.current?.health?.update(camera, el.clientWidth, el.clientHeight, boxes.current, lines.current)
      renderer.render(scene, camera)
    }
    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight
      if (!w || !h) return
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); render()
    }
    const observer = new ResizeObserver(resize); observer.observe(el)
    stage.current = { camera, pivot, health: null, render }
    new FBXLoader().load(MODEL_URL, model => {
      if (disposed) { disposeTree(model); return }
      const box = new THREE.Box3().setFromObject(model)
      const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3())
      model.position.sub(center)
      const holder = new THREE.Group(); holder.add(model); holder.scale.setScalar(FIT_HEIGHT / (size.y || 1))
      pivot.add(holder)
      if (stage.current) {
        stage.current.health = new AstronautHealth(model, pivot)
        stage.current.health.setZones(zonesRef.current)
      }
      setStatus('ready'); resize()
    }, undefined, () => {
      if (disposed) return
      setStatus('error'); setProblem('The 3D model could not be loaded (models/astronaut/astronaut.fbx).')
    })
    resize()
    return () => { disposed = true; observer.disconnect(); stage.current?.health?.dispose(); stage.current = null; disposeTree(scene); renderer.dispose() }
  }, [])

  useEffect(() => {
    const current = stage.current
    if (!current?.health) return
    current.health.setZones(zones)
    current.render()
  }, [zones, status])

  function clickMarker(e: React.PointerEvent<HTMLCanvasElement>) {
    const start = press.current, current = stage.current; press.current = null
    if (!start || !current || !current.health || Math.hypot(e.clientX - start.x, e.clientY - start.y) > 6) return
    const box = e.currentTarget.getBoundingClientRect(), ray = new THREE.Raycaster()
    ray.setFromCamera(new THREE.Vector2((e.clientX - box.left) / box.width * 2 - 1, -((e.clientY - box.top) / box.height) * 2 + 1), current.camera)
    const id = current.health.hit(ray)
    if (id) onSelect(id)
  }

  useEffect(() => {
    const current = stage.current
    if (!current) return
    current.pivot.rotation.set(pitch, angle, 0)
    current.camera.zoom = zoom; current.camera.updateProjectionMatrix()
    current.render()
  }, [angle, pitch, zoom, status])

  const views = [['Front', 0], ['Left side', Math.PI / 2], ['Back', Math.PI], ['Right side', -Math.PI / 2]] as const
  return <><div className="astronaut-presets" aria-label="Body viewing angle">{views.map(([label, value]) => <button key={label} aria-pressed={Math.abs(angle - value) < .01} onClick={() => { setAngle(value); setPitch(0) }}>{label}</button>)}</div>
    <div className="astronaut-stage"><div className="astronaut-orbit"/>
      <canvas ref={canvas} role="img" aria-label="Three-dimensional astronaut with bone-attached health auras. Drag to rotate. Arrow keys and the metric callout buttons are supported." tabIndex={0}
        onPointerDown={e => { drag.current = { x: e.clientX, y: e.clientY }; press.current = { x: e.clientX, y: e.clientY }; e.currentTarget.setPointerCapture(e.pointerId) }}
        onPointerMove={e => { const last = drag.current; if (!last) return; const dx = e.clientX - last.x, dy = e.clientY - last.y; drag.current = { x: e.clientX, y: e.clientY }; setAngle(a => a + dx * .012); setPitch(p => Math.max(-.5, Math.min(.5, p + dy * .006))) }}
        onPointerUp={e => { drag.current = null; clickMarker(e) }} onPointerCancel={() => { drag.current = null; press.current = null }}
        onKeyDown={e => { if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) { e.preventDefault(); e.stopPropagation(); const k = e.key; if (k === 'ArrowLeft' || k === 'ArrowRight') setAngle(a => a + (k === 'ArrowLeft' ? -.15 : .15)); else setPitch(p => Math.max(-.5, Math.min(.5, p + (k === 'ArrowUp' ? -.1 : .1)))) } }}/>
      {status !== 'ready' && <p className="astronaut-stage-label" role={status === 'error' ? 'alert' : 'status'} style={{ top: '50%', left: 0, right: 0, textAlign: 'center' }}>{status === 'loading' ? 'Loading 3D model…' : problem}</p>}
      <span className="astronaut-stage-label">360° / HEALTH VIEW</span>
      <div className="health-callouts" hidden={status !== 'ready'}>
        <svg className="health-leaders" width="100%" height="100%" aria-hidden="true">{zones.map(zone => <polyline key={zone.location} ref={node => { if (node) lines.current.set(zone.location, node); else lines.current.delete(zone.location) }} fill="none" stroke={HEALTH_COLORS[zone.tone]} strokeWidth="1.2" />)}</svg>
        {zones.map(zone => <div key={zone.location} className="health-callout" data-location={zone.location} data-tone={zone.tone} style={{ '--health-color': HEALTH_COLORS[zone.tone] } as CSSProperties} ref={node => { if (node) boxes.current.set(zone.location, node); else boxes.current.delete(zone.location) }}>
          <span className="health-callout-title">{zone.location === 'chest' ? 'Cardiovascular' : zone.location === 'lungs' ? 'Respiratory' : 'Wellbeing'}</span>
          {zone.signals.map(signal => <button key={signal.id} data-tone={signal.tone} aria-pressed={selected === signal.id} onClick={() => onSelect(signal.id)}>
            <span className="health-metric-name">{signal.label}<strong>{signal.value}</strong></span>
            <span className="health-metric-status" style={{ color: HEALTH_COLORS[signal.tone] }}>{signal.message}</span>
          </button>)}
        </div>)}
      </div></div>
    <div className="astronaut-toolbar"><span>Drag to rotate · Arrow keys supported</span><button aria-label="Zoom out" disabled={zoom <= .8} onClick={() => setZoom(z => Math.max(.8, z - .1))}>−</button><button aria-label="Zoom in" disabled={zoom >= 1.3} onClick={() => setZoom(z => Math.min(1.3, z + .1))}>+</button><button onClick={() => { setAngle(-.3); setPitch(0); setZoom(1) }}>Reset</button></div>
    <p className="astronaut-credit" style={{ fontSize: 11, textAlign: 'center', margin: '0 0 12px', color: '#c4d6e1' }}>Model: <a href={MODEL_SOURCE} target="_blank" rel="noopener noreferrer">“astronaut” by Antropik</a> (Sketchfab), <a href={LICENSE_URL} target="_blank" rel="noopener noreferrer">CC BY 4.0</a>.</p></>
}
