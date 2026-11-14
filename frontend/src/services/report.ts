import type { Assessment, CheckIn } from '../types/assessment'
// A small text-only PDF writer using the standard Helvetica font; no runtime dependency.
export function downloadReport(assessment: Assessment, submission?: CheckIn) {
  const lines = ['CREW HEALTH COMPASS', `${assessment.astronautId} / ${assessment.timepoint}`, 'Research prototype, not a diagnostic device.', 'Status classifications are simulated API fixtures; assessment rules are pending.', '']
  for (const system of assessment.systems) {
    lines.push(system.name, `Status: ${system.status} (${system.statusProvenance})`, system.reason, `Next step: ${system.action}`)
    const marker = system.markers.find(m => m.id === system.defaultMarker)
    if (marker) lines.push(`${marker.name}: ${marker.value ?? 'missing'} ${marker.unit}; baseline: ${marker.baseline ?? 'missing'} (${marker.baselineCount}/3 pre-flight visits).`, `Provenance: ${marker.provenance}`, `Source: ${marker.source.title}`, `Trend: ${marker.trend.map(p => `${p.time} ${p.value ?? 'missing'}`).join('; ')}`, `Supplied interval: ${marker.reference.low ?? 'unbounded'} to ${marker.reference.high ?? 'unbounded'} ${marker.unit}`)
    lines.push('')
  }
  if (submission) lines.push('Latest daily check-in', submission.timestamp, `Provenance: ${submission.provenance}`, ...Object.entries(submission.values).map(([k, v]) => `${k}: ${v}`), 'Clinical assessment pending. Not transmitted.')
  lines.push('Baseline: median of available L-92, L-44 and L-3 values.', 'https://osdr.nasa.gov/bio/repo/data/studies/OSD-575')
  const wrapped = lines.flatMap(line => {
    const ascii = line.replace(/[^\x20-\x7e]/g, '-')
    return ascii.match(/.{1,88}(?:\s|$)|.{1,88}/g)?.map(s => s.trim()) || ['']
  })
  const pages = Array.from({ length: Math.ceil(wrapped.length / 47) }, (_, i) => wrapped.slice(i * 47, (i + 1) * 47))
  const objects: string[] = ['', '', '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
  const pageIds: number[] = []
  pages.forEach(page => {
    const pageId = objects.length + 1, contentId = pageId + 1; pageIds.push(pageId)
    const escape = (s: string) => s.replace(/([\\()])/g, '\\$1')
    const stream = `BT /F1 10 Tf 14 TL 44 792 Td ${page.map((line, i) => `${i ? 'T* ' : ''}(${escape(line)}) Tj`).join('\n')} ET`
    objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents ${contentId} 0 R >>`, `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`)
  })
  objects[0] = '<< /Type /Catalog /Pages 2 0 R >>'; objects[1] = `<< /Type /Pages /Kids [${pageIds.map(id => `${id} 0 R`).join(' ')}] /Count ${pages.length} >>`
  let pdf = '%PDF-1.4\n'; const offsets = [0]
  objects.forEach((object, i) => { offsets.push(pdf.length); pdf += `${i + 1} 0 obj\n${object}\nendobj\n` })
  const xref = pdf.length; pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.slice(1).map(n => `${String(n).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`
  const url = URL.createObjectURL(new Blob([pdf], { type: 'application/pdf' })), a = document.createElement('a')
  a.href = url; a.download = `Crew-Health-${assessment.astronautId}-${assessment.timepoint}.pdf`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
