import { useMemo, useRef, useState } from 'react'
import { utcLabel, withSeparators } from '../services/radiation'
import type { RadiationPoint } from '../services/radiation'

// Drawing only: every value comes from the API; nothing is interpolated or computed for display.
const W = 960, H = 360, LEFT = 72, RIGHT = 20, TOP = 26, BOTTOM = 44
const HOUR = 3_600_000, DAY = 24 * HOUR
const GAP_MS = 3 * HOUR // break the line where readings are more than 3 h apart (they are usually 17 min apart)
const MIN_ZOOM_MS = 30 * 60_000

interface Pt { p: RadiationPoint; t: number; v: number | null }
interface Props { points: RadiationPoint[]; unit: string; detector: string; eventDate: string | null; peak: RadiationPoint | null; logScale: boolean }

function linearTicks(max: number) {
  const raw = max / 5, base = 10 ** Math.floor(Math.log10(raw)), step = [1, 2, 5, 10].map(m => m * base).find(s => s >= raw) ?? raw
  return Array.from({ length: Math.floor(max / step) + 1 }, (_, i) => i * step)
}
function timeTicks(x0: number, x1: number) {
  const step = [HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR, DAY, 2 * DAY, 7 * DAY, 14 * DAY].find(s => (x1 - x0) / s <= 8) ?? 28 * DAY
  const out: number[] = []
  for (let t = Math.ceil(x0 / step) * step; t <= x1; t += step) out.push(t)
  return { step, out }
}
const dateLabel = (t: number, step: number) => {
  const d = new Date(t), day = d.toLocaleDateString('en-US', { month: 'short', day: '2-digit', timeZone: 'UTC' })
  return step >= DAY ? day : `${day} ${d.toISOString().slice(11, 16)}`
}

export default function RadiationChart({ points, unit, detector, eventDate, peak, logScale }: Props) {
  const svg = useRef<SVGSVGElement>(null)
  const all = useMemo<Pt[]>(() => points.map(p => ({ p, t: Date.parse(p.timestamp_utc), v: p.value == null ? null : Number(p.value) })), [points])
  const [view, setView] = useState<[number, number] | null>(null)
  const [hover, setHover] = useState<Pt | null>(null)
  const [drag, setDrag] = useState<{ from: number; to: number } | null>(null)
  if (!all.length) return <p className="nasa-muted">No readings in this date range.</p>

  const full: [number, number] = [all[0].t, all[all.length - 1].t]
  const [x0, x1] = view ?? (full[0] === full[1] ? [full[0] - HOUR, full[1] + HOUR] : full)
  const visible = all.filter(q => q.t >= x0 && q.t <= x1)
  const values = visible.flatMap(q => q.v == null || (logScale && q.v <= 0) ? [] : [q.v])
  const vmax = values.length ? Math.max(...values) : 1, vmin = values.length ? Math.min(...values) : 1
  const [y0, y1] = logScale ? [Math.log10(vmin * 0.8), Math.log10(vmax * 1.25)] : [0, vmax * 1.08 || 1]
  const px = (t: number) => LEFT + (t - x0) / (x1 - x0 || 1) * (W - LEFT - RIGHT)
  const py = (v: number) => H - BOTTOM - ((logScale ? Math.log10(v) : v) - y0) / (y1 - y0 || 1) * (H - TOP - BOTTOM)
  const toTime = (sx: number) => x0 + (Math.min(Math.max(sx, LEFT), W - RIGHT) - LEFT) / (W - LEFT - RIGHT) * (x1 - x0)

  let path = '', prev: Pt | null = null
  const gaps: [number, number][] = []
  for (const q of visible) {
    if (q.v == null || (logScale && q.v <= 0)) { prev = null; continue } // a missing reading is a gap, never a value
    const jump = prev !== null && q.t - prev.t > GAP_MS
    if (jump && prev) gaps.push([prev.t, q.t])
    path += `${!prev || jump ? 'M' : 'L'}${px(q.t).toFixed(1)} ${py(q.v).toFixed(1)}`
    prev = q
  }
  const yTicks = logScale ? [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000].filter(v => Math.log10(v) >= y0 && Math.log10(v) <= y1) : linearTicks(y1)
  const { step, out: xTicks } = timeTicks(x0, x1)
  const eventStart = eventDate ? Date.parse(`${eventDate}T00:00:00Z`) : null
  const band = eventStart === null ? null : [Math.max(eventStart, x0), Math.min(eventStart + DAY, x1)] as const
  const peakT = peak ? Date.parse(peak.timestamp_utc) : null, peakV = peak?.value == null ? null : Number(peak.value)
  const dataEnd = full[1]

  function svgX(e: React.PointerEvent) { const box = svg.current!.getBoundingClientRect(); return (e.clientX - box.left) / box.width * W }
  function nearest(t: number) {
    let lo = 0, hi = visible.length - 1
    while (lo < hi) { const mid = (lo + hi) >> 1; if (visible[mid].t < t) lo = mid + 1; else hi = mid }
    return lo > 0 && t - visible[lo - 1].t < visible[lo].t - t ? visible[lo - 1] : visible[lo]
  }
  return <div className="rad-chart">
    <svg ref={svg} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Detector ${detector} absorbed dose rate in ${unit}, ${visible.length} readings from ${utcLabel(new Date(x0).toISOString())} to ${utcLabel(new Date(x1).toISOString())}. Line breaks mark periods without readings.`}>
      <defs><clipPath id={`rad-plot-${detector}`}><rect x={LEFT} y={TOP} width={W - LEFT - RIGHT} height={H - TOP - BOTTOM} /></clipPath></defs>
      {yTicks.map(v => <g key={v} className="rad-grid"><line x1={LEFT} x2={W - RIGHT} y1={py(v)} y2={py(v)} /><text x={LEFT - 8} y={py(v) + 4} textAnchor="end">{v.toLocaleString('en-US')}</text></g>)}
      {xTicks.map(t => <text key={t} className="rad-axis" x={px(t)} y={H - BOTTOM + 18} textAnchor="middle">{dateLabel(t, step)}</text>)}
      <text className="rad-axis" x={14} y={TOP + (H - TOP - BOTTOM) / 2} transform={`rotate(-90 14 ${TOP + (H - TOP - BOTTOM) / 2})`} textAnchor="middle">{unit} (dose rate)</text>
      <g clipPath={`url(#rad-plot-${detector})`}>
        {gaps.map(([a, b]) => <rect key={a} className="rad-gap" x={px(a)} y={TOP} width={Math.max(px(b) - px(a), 1)} height={H - TOP - BOTTOM}><title>No readings from {utcLabel(new Date(a).toISOString())} to {utcLabel(new Date(b).toISOString())}</title></rect>)}
        {band && band[1] > band[0] && <rect className="rad-event" x={px(band[0])} y={TOP} width={px(band[1]) - px(band[0])} height={H - TOP - BOTTOM} />}
        <path className="rad-line" d={path} />
        {peakT !== null && peakV !== null && peakT >= x0 && peakT <= x1 && <circle className="rad-peak" cx={px(peakT)} cy={py(peakV)} r={5} />}
        {hover && hover.v !== null && <circle className="rad-hover" cx={px(hover.t)} cy={py(hover.v)} r={4} />}
        {drag && <rect className="rad-select" x={Math.min(drag.from, drag.to)} y={TOP} width={Math.abs(drag.to - drag.from)} height={H - TOP - BOTTOM} />}
      </g>
      {band && band[1] > band[0] && <text className="rad-event-label" x={px(band[0]) - 6} y={TOP + 14} textAnchor="end">{eventDate} solar event ▸</text>}
      {dataEnd <= x1 && dataEnd >= x0 && <g className="rad-end"><line x1={px(dataEnd)} x2={px(dataEnd)} y1={TOP} y2={H - BOTTOM} /><text x={px(dataEnd) - 6} y={H - BOTTOM - 8} textAnchor="end">export ends {utcLabel(new Date(dataEnd).toISOString())}</text></g>}
      <rect className="rad-overlay" x={LEFT} y={TOP} width={W - LEFT - RIGHT} height={H - TOP - BOTTOM}
        onPointerDown={e => { if (e.button !== 0) return; e.currentTarget.setPointerCapture(e.pointerId); const x = svgX(e); setDrag({ from: x, to: x }); setHover(null) }}
        onPointerMove={e => { const x = svgX(e); if (drag) setDrag({ ...drag, to: x }); else if (visible.length) setHover(nearest(toTime(x))) }}
        onPointerUp={() => { if (drag && Math.abs(drag.to - drag.from) > 8) { const a = toTime(Math.min(drag.from, drag.to)), b = toTime(Math.max(drag.from, drag.to)); setView(b - a < MIN_ZOOM_MS ? [a - MIN_ZOOM_MS / 2, b + MIN_ZOOM_MS / 2] : [a, b]) } setDrag(null) }}
        onPointerLeave={() => { if (!drag) setHover(null) }} />
    </svg>
    {hover && !drag && <div className="rad-tooltip" style={{ left: `${Math.min(Math.max(px(hover.t) / W * 100, 12), 88)}%` }}><strong>{hover.p.value == null ? `No value (${hover.p.value_status})` : `${withSeparators(hover.p.value)} ${unit}`}</strong><span>{utcLabel(hover.p.timestamp_utc)} · detector {hover.p.detector}</span></div>}
    <div className="rad-chart-footer"><span>{visible.length.toLocaleString('en-US')} readings shown · drag across the chart to zoom</span>{view && <button type="button" onClick={() => setView(null)}>Reset zoom</button>}</div>
  </div>
}
