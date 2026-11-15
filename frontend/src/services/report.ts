import type { MonitoringResult } from './monitoring'
// A small text-only PDF writer using the standard Helvetica font; no runtime dependency.
/** `example` is null for a stored check-in: whether it used example values is not recorded. */
export function downloadMonitoringReport(result: MonitoringResult, example: boolean | null) {
  const lines = ['CREW HEALTH COMPASS - MODE 1 MISSION HEALTH MONITOR', `${result.astronaut_id} / ${result.activity_context} / ${result.timestamp}`, 'Research prototype, not a diagnostic device.',
    'Statistical comparison with synthetic personal history (fictional crew and readings).', `Input: ${example === null ? 'stored check-in (example or user-entered: not recorded)' : example ? 'example values filled by the app' : 'user-entered'}`, '',
    `Overall status: ${result.overall_status}`, `Affected systems: ${result.affected_systems.join(', ') || 'none'}`, `Body marker: ${result.body_marker ?? 'none'}`, result.explanation, '']
  for (const e of result.evidence) {
    const s = e.statistics
    lines.push(`${e.indicator}: ${e.value ?? e.category ?? 'unavailable'} ${e.value != null ? e.unit : ''}; baseline: ${e.baseline ?? 'unavailable'}`,
      s ? `  status ${s.status}; robust z ${s.robust_z ?? 'unavailable'}; MAD ${s.mad ?? 'unavailable'}; ${s.observation_count} earlier readings; history: ${s.history_origins.join(', ')}` : '  not compared')
  }
  lines.push('', 'Limitations:', ...result.insufficient_data.map(r => `- ${r}`), '', `Next action: ${result.next_action_protocol_id ?? 'no approved action protocol; exploratory monitoring finding, not a diagnosis.'}`)
  savePdf(lines, `Crew-Health-${result.astronaut_id}-${result.timestamp.slice(0, 16).replace(/[^0-9T]/g, '')}.pdf`)
}

function savePdf(lines: string[], filename: string) {
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
  a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
