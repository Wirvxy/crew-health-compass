import type { Marker } from '../types/assessment'
export const formatNumber = (value: number | null) => value == null ? '—' : new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 }).format(value)
const compact = (value: number) => new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 }).format(value)
export default function TrendChart({ marker: m, visit }: { marker: Marker; visit: string }) {
  const values = m.trend.flatMap(p => p.value == null ? [] : [p.value])
  if (!values.length) return <p className="details-note">No measured trend available.</p>
  for (const value of [m.baseline, m.reference.low, m.reference.high]) if (value != null) values.push(value)
  let low = Math.min(...values), high = Math.max(...values)
  const pad = (high - low) * .18 || 1; low -= pad; high += pad
  const x = (i: number) => 48 + i * 57, y = (v: number) => 143 - (v - low) / (high - low) * 112
  let path = '', gap = true
  m.trend.forEach((p, i) => { if (p.value == null) { gap = true; return }; path += `${gap ? 'M' : 'L'}${x(i)} ${y(p.value)} `; gap = false })
  const hasRange = m.reference.low != null || m.reference.high != null
  const top = m.reference.high == null ? 26 : y(m.reference.high), bottom = m.reference.low == null ? 147 : y(m.reference.low)
  return <div className="chart-block"><div className="chart-caption"><span>PERSONAL TREND</span><span>{m.provenance === 'simulated' ? 'SYNTHETIC FIXTURE' : 'RECORDED ASSAYS'}</span></div>
    <svg className="chart" viewBox="0 0 350 185" role="img" aria-label={`${m.name}: ${m.trend.map(p => `${p.time}: ${formatNumber(p.value)} ${m.unit}`).join('; ')}`}>
      {[.2, .6, 1].map(q => { const value = low + (high - low) * q; return <g key={q}><line className="grid" x1="46" x2="337" y1={y(value)} y2={y(value)} /><text x="0" y={y(value) + 3}>{compact(value)}</text></g> })}
      {hasRange && <rect className="reference" x="46" y={top} width="290" height={Math.max(1, bottom - top)} />}
      {m.baseline != null && <line className="baseline" x1="46" x2="337" y1={y(m.baseline)} y2={y(m.baseline)} />}
      <path className="trend" d={path} />
      {m.trend.map((p, i) => <g key={p.time}>{p.value != null && <circle className="point" cx={x(i)} cy={y(p.value)} r={p.time === visit ? 4.5 : 2.5}><title>{p.time}: {formatNumber(p.value)} {m.unit}</title></circle>}<text x={x(i)} y="171" textAnchor="middle">{p.time}</text></g>)}
    </svg><div className="chart-key"><span><i className="key-line" />Measured</span><span><i className="key-line dashed" />Baseline</span>{hasRange && <span><i className="key-line ref" />Reference</span>}</div>
    <div className="micro">{hasRange ? `Supplied interval: ${m.reference.low == null ? 'unbounded' : formatNumber(m.reference.low)} – ${m.reference.high == null ? 'unbounded' : formatNumber(m.reference.high)} ${m.unit}` : 'No clinical reference interval supplied.'}</div>
  </div>
}
