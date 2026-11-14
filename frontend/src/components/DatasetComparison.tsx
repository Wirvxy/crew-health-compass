import { chartNumber } from '../services/dataset'
/** Frontend display model, NOT an assumed backend response schema. */
export interface DatasetComparisonView {
  value: string | null; baseline: string | null; change: string | null; unit: string
  baselineMethod: string; baselineStatus: string; laboratoryStatus: string | null
  provenance: string; source: {title: string; url: string}; mode: 'local-preview' | 'api'
}
const display = (raw: string | null, signed = false) => {
  const value = chartNumber(raw)
  return value == null ? 'Unavailable' : new Intl.NumberFormat('en-US', {maximumFractionDigits: 2, signDisplay: signed ? 'exceptZero' : 'auto'}).format(value)
}
export default function DatasetComparison({data}: {data: DatasetComparisonView}) {
  return <section className="dataset-comparison" aria-label="Historical laboratory comparison"><p className="eyebrow">HISTORICAL LABORATORY COMPARISON</p><p className="micro">{data.mode === 'local-preview' ? 'Local dataset preview · proposed API not connected' : 'Dataset API response'}</p><dl><div><dt>Measurement</dt><dd>{display(data.value)} {data.unit}</dd></div><div><dt>Personal baseline</dt><dd>{display(data.baseline)} {data.unit}</dd></div><div><dt>Change from baseline</dt><dd>{display(data.change, true)} {data.unit}</dd></div><div><dt>Laboratory comparison</dt><dd>{data.laboratoryStatus ?? 'Pending API response'}</dd></div></dl><p className="micro">Baseline: {data.baselineMethod} · {data.baselineStatus}</p><p className="micro">Provenance: {data.provenance}</p><a href={data.source.url} target="_blank" rel="noopener noreferrer">{data.source.title}</a><p className="details-note">Historical laboratory comparisons are not diagnoses or treatment recommendations.</p></section>
}
