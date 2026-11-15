import type { RadiationStatistics } from '../services/radiation'
import { utcLabel } from '../services/radiation'

interface Props {
  statistics: RadiationStatistics | null
  unit: string
  start: string | null
  end: string | null
}

function value(raw: string | null) {
  if (raw === null) return 'Unavailable'
  const number = Number(raw)
  if (!Number.isFinite(number)) return 'Unavailable'
  return <span title={`Exact value: ${raw}`}>{new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(number)}</span>
}

export default function RadiationRangeSummary({ statistics, unit, start, end }: Props) {
  if (!statistics) return <p className="nasa-muted">Statistics are unavailable for this range.</p>
  const s = statistics
  return <section className="rad-range-summary" aria-label="Selected range statistics">
    <h4>Selected range</h4>
    <p className="nasa-muted">{start && end ? `${utcLabel(start)} to ${utcLabel(end)}` : 'No readings in this range.'}</p>
    <dl className="nasa-metrics">
      <div><dt>Recorded readings</dt><dd>{s.observation_count.toLocaleString('en-US')}</dd><span>{s.valid_count.toLocaleString('en-US')} valid · {s.missing_count} missing · {s.invalid_count} invalid</span></div>
      <div><dt>Sample median</dt><dd>{value(s.median)} <small>{unit}</small></dd><span>Middle recorded value</span></div>
      <div><dt>Mean of samples</dt><dd>{value(s.mean)} <small>{unit}</small></dd><span>Equal weight for each valid reading</span></div>
      <div><dt>Highest recorded rate</dt><dd>{value(s.max)} <small>{unit}</small></dd><span>{s.peak ? utcLabel(s.peak.timestamp_utc) : 'No valid reading'}</span></div>
    </dl>
    <p className="nasa-muted">Sampling intervals vary. These statistics describe recorded dose rates at this detector.</p>
  </section>
}
