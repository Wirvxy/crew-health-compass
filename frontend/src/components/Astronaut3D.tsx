import { useEffect, useRef, useState } from 'react'
type V = [number, number, number]
type Face = { points: V[]; color: number[] }
// Original procedural geometry; no remote model, runtime library or inferred clinical signals.
function buildAstronaut() {
  const faces: Face[] = []
  function ellipsoid(c: V, r: V, color: number[], tilt = 0) {
    const point = (u: number, v: number): V => { const x = r[0]*Math.sin(v)*Math.cos(u), y = r[1]*Math.cos(v); return [c[0]+x*Math.cos(tilt)-y*Math.sin(tilt), c[1]+x*Math.sin(tilt)+y*Math.cos(tilt), c[2]+r[2]*Math.sin(v)*Math.sin(u)] }
    for(let i=0;i<32;i++) for(let j=0;j<20;j++) { const a=i*Math.PI/16,b=j*Math.PI/20; faces.push({points:[point(a,b),point(a+Math.PI/16,b),point(a+Math.PI/16,b+Math.PI/20),point(a,b+Math.PI/20)],color}) }
  }
  const suit=[190,210,223], seam=[56,87,108], trim=[133,205,199]
  ellipsoid([0,.7,-.28],[.43,.66,.22],seam) // life-support pack
  ellipsoid([0,.72,0],[.48,.69,.28],suit)
  ellipsoid([0,.1,0],[.39,.28,.25],seam)
  ellipsoid([0,1.38,0],[.25,.09,.24],trim)
  ellipsoid([0,1.74,0],[.35,.4,.32],suit)
  ellipsoid([0,1.78,.245],[.275,.255,.13],[24,55,76]) // forward visor
  ellipsoid([-.12,1.9,.35],[.075,.045,.015],[147,208,221])
  ellipsoid([0,.84,.254],[.25,.25,.055],[64,98,117])
  for(const side of [-1,1]) {
    ellipsoid([side*.49,1.12,0],[.19,.23,.21],suit)
    ellipsoid([side*.63,.77,0],[.16,.39,.17],suit,side*.28)
    ellipsoid([side*.76,.4,.015],[.15,.12,.15],seam)
    ellipsoid([side*.82,.12,.035],[.145,.31,.15],suit,side*.13)
    ellipsoid([side*.87,-.15,.045],[.15,.08,.15],trim)
    ellipsoid([side*.89,-.32,.065],[.145,.19,.125],suit)
    ellipsoid([side*.24,-.43,0],[.195,.49,.21],suit,side*.05)
    ellipsoid([side*.27,-.88,.02],[.175,.13,.19],seam)
    ellipsoid([side*.28,-1.22,0],[.17,.34,.18],suit)
    ellipsoid([side*.29,-1.56,.1],[.185,.18,.3],suit)
    ellipsoid([side*.29,-1.68,.11],[.19,.06,.31],seam)
  }
  return faces
}
const model = buildAstronaut()
export default function Astronaut3D() {
  const canvas=useRef<HTMLCanvasElement>(null), drag=useRef<{x:number;y:number}|null>(null)
  const [angle,setAngle]=useState(-.3),[pitch,setPitch]=useState(0),[zoom,setZoom]=useState(1)
  useEffect(()=>{
    const el=canvas.current; if(!el)return
    const render=()=>{
      const w=el.clientWidth,h=el.clientHeight,dpr=Math.min(window.devicePixelRatio||1,2); el.width=w*dpr;el.height=h*dpr
      const ctx=el.getContext('2d');if(!ctx)return;ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h)
      const s=Math.min(w/2.65,h/4.5)*zoom
      function rotate(p:V):V {const x=p[0]*Math.cos(angle)+p[2]*Math.sin(angle),z=-p[0]*Math.sin(angle)+p[2]*Math.cos(angle);return [x,p[1]*Math.cos(pitch)-z*Math.sin(pitch),p[1]*Math.sin(pitch)+z*Math.cos(pitch)]}
      const projected=model.map(f=>({p:f.points.map(rotate),color:f.color})).sort((a,b)=>a.p.reduce((s,p)=>s+p[2],0)-b.p.reduce((s,p)=>s+p[2],0))
      for(const f of projected){const a=f.p[0],b=f.p[1],c=f.p[2],u=b.map((n,i)=>n-a[i]),v=c.map((n,i)=>n-a[i]);const normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],len=Math.hypot(...normal)||1;const light=.55+.45*Math.abs((normal[0]*-.4+normal[1]*.6+normal[2]*.7)/len);ctx.fillStyle=`rgb(${f.color.map(n=>Math.round(n*light)).join(',')})`;ctx.beginPath();f.p.forEach((p,i)=>{const perspective=6/(6-p[2]);const x=w/2+p[0]*s*perspective,y=h/2-(p[1]-.15)*s*perspective;i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.closePath();ctx.fill();ctx.strokeStyle=ctx.fillStyle;ctx.lineWidth=.45;ctx.stroke()}
    };const observer=new ResizeObserver(render);observer.observe(el);render();return()=>observer.disconnect()
  },[angle,pitch,zoom])
  const views=[['Front',0],['Left side',Math.PI/2],['Back',Math.PI],['Right side',-Math.PI/2]] as const
  return <><div className="astronaut-presets" aria-label="Body viewing angle">{views.map(([label,value])=><button key={label} aria-pressed={Math.abs(angle-value)<.01} onClick={()=>{setAngle(value);setPitch(0)}}>{label}</button>)}</div><div className="astronaut-stage"><div className="astronaut-orbit"/><canvas ref={canvas} role="img" aria-label="Three-dimensional astronaut in a neutral flight suit. Drag to rotate, or use arrow keys and view buttons. Body parts are not selectable." tabIndex={0} onPointerDown={e=>{drag.current={x:e.clientX,y:e.clientY};e.currentTarget.setPointerCapture(e.pointerId)}} onPointerMove={e=>{if(!drag.current)return;setAngle(a=>a+(e.clientX-drag.current!.x)*.012);setPitch(p=>Math.max(-.5,Math.min(.5,p+(e.clientY-drag.current!.y)*.006)));drag.current={x:e.clientX,y:e.clientY}}} onPointerUp={()=>{drag.current=null}} onPointerCancel={()=>{drag.current=null}} onKeyDown={e=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();e.stopPropagation();if(e.key==='ArrowLeft'||e.key==='ArrowRight')setAngle(a=>a+(e.key==='ArrowLeft'?-.15:.15));else setPitch(p=>Math.max(-.5,Math.min(.5,p+(e.key==='ArrowUp'?-.1:.1))))}}}/><span className="astronaut-stage-label">360° / SPATIAL VIEW</span></div><div className="astronaut-toolbar"><span>Drag to rotate · Arrow keys supported</span><button aria-label="Zoom out" disabled={zoom<=.8} onClick={()=>setZoom(z=>Math.max(.8,z-.1))}>−</button><button aria-label="Zoom in" disabled={zoom>=1.3} onClick={()=>setZoom(z=>Math.min(1.3,z+.1))}>+</button><button onClick={()=>{setAngle(-.3);setPitch(0);setZoom(1)}}>Reset</button></div></>
}
