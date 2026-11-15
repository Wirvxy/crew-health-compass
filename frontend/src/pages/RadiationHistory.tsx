import { useEffect, useState } from 'react'
import RadiationChart from '../components/RadiationChart'
import { may20Event, RadiationApiError, radiationTimeline, utcLabel, withSeparators } from '../services/radiation'
import type { RadiationEvent, RadiationTimeline } from '../services/radiation'

// Mission Environment: historical Mars measurements only. Nothing here feeds Mode 1 or Mode 2.
const LIMITATION = 'Historical Curiosity RAD detector measurements. These values describe the Martian radiation environment, not personal astronaut exposure or medical risk. Sampling is irregular, and the CSV export does not retain all original quality metadata.'
type Range = { start: string; end: string }
const message = (e: unknown) => e instanceof RadiationApiError ? (e.status ? `Radiation API ${e.status}: ${e.message}` : e.message) : 'Unable to load the radiation history.'

export default function RadiationHistory({ active }: { active: boolean }) {
  const [started, setStarted] = useState(false)
  useEffect(() => { if (active) setStarted(true) }, [active]) // load only once the tab is first opened
  const [range, setRange] = useState<Range>({ start: '', end: '' }), [draft, setDraft] = useState<Range>({ start: '', end: '' })
  const [bounds, setBounds] = useState<Range | null>(null)
  const [timeline, setTimeline] = useState<{ key: string; data?: RadiationTimeline; error?: string } | null>(null)
  const [event, setEvent] = useState<{ data?: RadiationEvent; error?: string } | null>(null)
  const [retry, setRetry] = useState(0), [logScale, setLogScale] = useState(false)
  const key = `${range.start}/${range.end}/${retry}`
  useEffect(() => {
    if (!started) return
    const c = new AbortController()
    radiationTimeline(range, c.signal).then(data => {
      if (c.signal.aborted) return
      setTimeline({ key, data })
      const s = data.series[0]
      if (!range.start && !range.end && s?.start_timestamp_utc && s.end_timestamp_utc) setBounds({ start: s.start_timestamp_utc.slice(0, 10), end: s.end_timestamp_utc.slice(0, 10) })
    }).catch(e => { if (!c.signal.aborted) setTimeline({ key, error: message(e) }) })
    return () => c.abort()
  }, [started, range, retry, key])
  useEffect(() => {
    if (!started) return
    const c = new AbortController()
    may20Event(c.signal).then(data => { if (!c.signal.aborted) setEvent({ data }) }).catch(e => { if (!c.signal.aborted) setEvent({ error: message(e) }) })
    return () => c.abort()
  }, [started, retry])

  const data = timeline?.key === key ? timeline.data : undefined, error = timeline?.key === key ? timeline.error : undefined
  const ev = event?.data, evSeries = ev?.series[0], week = evSeries?.preceding_week_comparison
  function apply(next: Range) { setDraft(next); setRange(next) }
  const presets: [string, Range][] = [['Full record', { start: '', end: '' }], ...(ev && week ? [[`${week.start_date.slice(5)} to ${ev.event_date.slice(5)} (event week)`, { start: week.start_date, end: ev.event_date }], [`${ev.event_date} only`, { start: ev.event_date, end: ev.event_date }]] as [string, Range][] : [])]
  const ratio = week?.event_median_to_prior_median_ratio

  return <div className="nasa-page radiation-page">
    <p className="nasa-note">{LIMITATION}</p>
    <section className="nasa-panel" aria-labelledby="rad-chart-title">
      <p className="eyebrow">CURIOSITY RAD · ABSORBED DOSE RATE ON THE MARTIAN SURFACE</p>
      <h2 id="rad-chart-title">Radiation timeline</h2>
      <div className="rad-controls">
        <div className="rad-presets" role="group" aria-label="Date range presets">{presets.map(([label, r]) => <button key={label} type="button" aria-pressed={range.start === r.start && range.end === r.end} onClick={() => apply(r)}>{label}</button>)}</div>
        <form className="rad-range" onSubmit={e => { e.preventDefault(); setRange(draft) }}>
          <label>From (UTC)<input type="date" value={draft.start} min={bounds?.start} max={bounds?.end} onChange={e => setDraft(d => ({ ...d, start: e.target.value }))} /></label>
          <label>To (UTC)<input type="date" value={draft.end} min={bounds?.start} max={bounds?.end} onChange={e => setDraft(d => ({ ...d, end: e.target.value }))} /></label>
          <button type="submit">Apply dates</button>
        </form>
        <label className="rad-log"><input type="checkbox" checked={logScale} onChange={e => setLogScale(e.target.checked)} /> Logarithmic scale</label>
      </div>
      {error ? <div role="alert"><p>{error}</p><button type="button" onClick={() => setRetry(n => n + 1)}>Retry</button> <button type="button" onClick={() => apply({ start: '', end: '' })}>Show the full record</button></div>
        : !data ? <p role="status">Loading the Curiosity radiation record…</p>
        : data.series.length === 0 ? <p className="nasa-muted">No readings in this date range.</p>
        : data.series.map(s => <div key={s.detector}>
            <h3>Detector {s.detector} · {data.unit} (rate)</h3>
            <RadiationChart key={`${key}/${s.detector}`} points={s.observations} unit={data.unit} detector={s.detector} eventDate={ev?.event_date ?? null} peak={ev?.series.find(e => e.detector === s.detector)?.statistics.peak ?? null} logScale={logScale} />
          </div>)}
      <ul className="rad-legend"><li><span className="key-line" /> Recorded readings ({data?.observation_count.toLocaleString('en-US') ?? '…'} in range)</li><li><span className="key-band" /> May 20, 2024 event day</li><li><span className="key-gap" /> No readings for more than 3 hours</li><li><span className="key-end" /> End of the exported record</li></ul>
    </section>

    <section className="nasa-panel rad-event-card" aria-labelledby="rad-event-title">
      <p className="eyebrow">HISTORICAL EVENT · NASA CURIOSITY RAD</p>
      <h2 id="rad-event-title">May 20, 2024 — Solar Radiation Event</h2>
      {event?.error ? <div role="alert"><p>{event.error}</p><button type="button" onClick={() => setRetry(n => n + 1)}>Retry</button></div>
        : !ev || !evSeries ? <p role="status">Loading the event summary…</p>
        : <>
          <p>{ev.description} NASA documented a strong radiation surge during the May 20, 2024 solar event.</p>
          {ev.evidence_available ? <dl className="nasa-metrics">
            <div><dt>Highest detector {evSeries.detector} rate</dt><dd>{withSeparators(evSeries.statistics.peak?.value)} <small>{ev.unit}</small></dd><span>{evSeries.statistics.peak ? `at ${utcLabel(evSeries.statistics.peak.timestamp_utc)}` : 'No valid reading'}</span></div>
            <div><dt>May 20 sample median</dt><dd>{withSeparators(evSeries.statistics.median)} <small>{ev.unit}</small></dd><span>{evSeries.statistics.valid_count} readings on {ev.event_date}</span></div>
            <div><dt>{week ? `${week.start_date.slice(5)} to ${week.end_date.slice(5)}` : 'Preceding week'} sample median</dt><dd>{withSeparators(week?.median)} <small>{ev.unit}</small></dd><span>{week ? `${week.valid_sample_count} readings on ${week.observed_date_count} dates` : ''}</span></div>
            <div><dt>Comparison of medians</dt><dd title={ratio ? `Exact: ${ratio}` : undefined}>{ratio ? `${Number(ratio).toFixed(2)}×` : 'Not available'}</dd><span>May 20 median ÷ preceding-week median</span></div>
          </dl> : <p className="nasa-muted">This export has no valid readings for {ev.event_date}.</p>}
          <p className="nasa-muted">The exported record ends on {ev.event_date}, so the event’s later course is not covered. These are dose <strong>rates</strong> at one detector, not an accumulated dose.</p>
          <p><a href={ev.source_reference} target="_blank" rel="noopener noreferrer">NASA: Curiosity sees streaks and specks during 2024 solar storm ↗</a></p>
        </>}
    </section>

    <details className="nasa-panel">
      <summary>Data source and limitations</summary>
      {(data ?? ev) && <><ul>{(data ?? ev)!.limitations.map(l => <li key={l}>{l}</li>)}</ul>
        <p className="nasa-muted">{(data ?? ev)!.mission} · {(data ?? ev)!.instrument} · dataset {(data ?? ev)!.dataset_id}. File {(data ?? ev)!.source.csv_file}, SHA-256 {(data ?? ev)!.source.csv_sha256}. Every reading keeps its NASA source file URL.</p>
        <p><a href={(data ?? ev)!.source.dataset_url} target="_blank" rel="noopener noreferrer">NASA dataset catalogue ↗</a></p></>}
    </details>
    <footer className="nasa-footer"><span>Mission Environment: historical NASA observations. Separate from the health monitor: nothing here changes an astronaut status.</span><span>Research prototype, not a diagnostic device.</span></footer>
  </div>
}
