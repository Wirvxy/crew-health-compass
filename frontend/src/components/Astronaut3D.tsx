import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js'

// "Astronaut" by Javi_DaviYT on Sketchfab, CC BY 4.0 (see public/licenses/Astronaut-model-NOTICE.txt).
// The FBX and its textures are served by this app, so nothing is fetched from Sketchfab at runtime.
const MODEL_URL = `${import.meta.env.BASE_URL}models/astronaut/astronaut.fbx`
const MODEL_SOURCE = 'https://sketchfab.com/3d-models/astronaut-287589e324b942b8be57dbd6c539b2ab'
const LICENSE_URL = 'https://creativecommons.org/licenses/by/4.0/'
const FIT_HEIGHT = 2.6

type Status = 'loading' | 'ready' | 'error'
interface Stage { camera: THREE.PerspectiveCamera; pivot: THREE.Group; render: () => void }

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

export default function Astronaut3D() {
  const canvas = useRef<HTMLCanvasElement>(null), drag = useRef<{ x: number; y: number } | null>(null), stage = useRef<Stage | null>(null)
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
    const render = () => renderer.render(scene, camera)
    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight
      if (!w || !h) return
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); render()
    }
    const observer = new ResizeObserver(resize); observer.observe(el)
    stage.current = { camera, pivot, render }
    new FBXLoader().load(MODEL_URL, model => {
      if (disposed) { disposeTree(model); return }
      const box = new THREE.Box3().setFromObject(model)
      const size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3())
      model.position.sub(center)
      const holder = new THREE.Group(); holder.add(model); holder.scale.setScalar(FIT_HEIGHT / (size.y || 1))
      pivot.add(holder); setStatus('ready'); resize()
    }, undefined, () => {
      if (disposed) return
      setStatus('error'); setProblem('The 3D model could not be loaded (models/astronaut/astronaut.fbx).')
    })
    resize()
    return () => { disposed = true; observer.disconnect(); stage.current = null; disposeTree(scene); renderer.dispose() }
  }, [])

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
      <canvas ref={canvas} role="img" aria-label="Three-dimensional astronaut model. Drag to rotate, or use arrow keys and view buttons. Body parts are not selectable." tabIndex={0}
        onPointerDown={e => { drag.current = { x: e.clientX, y: e.clientY }; e.currentTarget.setPointerCapture(e.pointerId) }}
        onPointerMove={e => { const last = drag.current; if (!last) return; const dx = e.clientX - last.x, dy = e.clientY - last.y; drag.current = { x: e.clientX, y: e.clientY }; setAngle(a => a + dx * .012); setPitch(p => Math.max(-.5, Math.min(.5, p + dy * .006))) }}
        onPointerUp={() => { drag.current = null }} onPointerCancel={() => { drag.current = null }}
        onKeyDown={e => { if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) { e.preventDefault(); e.stopPropagation(); const k = e.key; if (k === 'ArrowLeft' || k === 'ArrowRight') setAngle(a => a + (k === 'ArrowLeft' ? -.15 : .15)); else setPitch(p => Math.max(-.5, Math.min(.5, p + (k === 'ArrowUp' ? -.1 : .1)))) } }}/>
      {status !== 'ready' && <p className="astronaut-stage-label" role={status === 'error' ? 'alert' : 'status'} style={{ top: '50%', left: 0, right: 0, textAlign: 'center' }}>{status === 'loading' ? 'Loading 3D model…' : problem}</p>}
      <span className="astronaut-stage-label">360° / SPATIAL VIEW</span></div>
    <div className="astronaut-toolbar"><span>Drag to rotate · Arrow keys supported</span><button aria-label="Zoom out" disabled={zoom <= .8} onClick={() => setZoom(z => Math.max(.8, z - .1))}>−</button><button aria-label="Zoom in" disabled={zoom >= 1.3} onClick={() => setZoom(z => Math.min(1.3, z + .1))}>+</button><button onClick={() => { setAngle(-.3); setPitch(0); setZoom(1) }}>Reset</button></div>
    <p className="astronaut-credit" style={{ fontSize: 11, textAlign: 'center', margin: '0 0 12px', color: '#c4d6e1' }}>Model: <a href={MODEL_SOURCE} target="_blank" rel="noopener noreferrer">“Astronaut” by Javi_DaviYT</a> (Sketchfab), <a href={LICENSE_URL} target="_blank" rel="noopener noreferrer">CC BY 4.0</a>.</p></>
}
