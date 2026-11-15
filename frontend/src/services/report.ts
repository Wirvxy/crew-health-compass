// Mode 1 check-in report: a designed A4 PDF built on this computer with pdf-lib, so nothing is sent anywhere.
// Every figure comes from the backend's assessment and the profile's saved check-ins; this file only lays them out.
// It runs in a Web Worker (reportWorker.ts), so pdf-lib loads only on export and the page never freezes.
import { PDFDocument, StandardFonts, rgb, setCharacterSpacing } from 'pdf-lib'
import type { PDFFont, PDFPage, RGB } from 'pdf-lib'
import fontkit from '@pdf-lib/fontkit'
import interRegular from '../assets/fonts/Inter-Regular.ttf?url'
import interMedium from '../assets/fonts/Inter-Medium.ttf?url'
import interBold from '../assets/fonts/Inter-Bold.ttf?url'
import logoUrl from '../assets/brand/crew-health-compass-logo.png?url'
import { STATUS_VIEW, words } from './monitoring'
import type { Evidence, MonitoringAstronauts, MonitoringResult } from './monitoring'
import type { StoredCheckIn } from './personal'
import { profileCode } from './session'
import type { Profile } from './session'

export interface ReportInput {
  result: MonitoringResult
  /** null for a saved check-in: whether it used example values is not recorded. */
  example: boolean | null
  profile: Profile
  recent: StoredCheckIn[] | null
  history: MonitoringAstronauts | null
}

const W = 595.28, H = 841.89, M = 42, CW = W - 2 * M, BOTTOM = 70 // A4 in points; content stops above the footer
const hex = (h: string) => rgb(parseInt(h.slice(1, 3), 16) / 255, parseInt(h.slice(3, 5), 16) / 255, parseInt(h.slice(5, 7), 16) / 255)
const C = { navy: hex('#0B1E2B'), ink: hex('#0E2233'), body: hex('#2A3B4C'), muted: hex('#66788A'), line: hex('#D6DEE6'), panel: hex('#F3F6F9'),
  white: hex('#FFFFFF'), cyan: hex('#22D3EE'), teal: hex('#0E8A9A'), mist: hex('#A9BCCB'), band: hex('#E2ECE7') }
// Same colour rules as the app: green, amber and grey; red only for an approved rule.
const TONES = {
  normal: { fg: hex('#1F7A55'), bg: hex('#E7F4EE'), short: 'No unusual pattern' },
  watch: { fg: hex('#9A5B00'), bg: hex('#FFF3DC'), short: 'Unusual' },
  unavailable: { fg: hex('#5B6875'), bg: hex('#EEF1F4'), short: 'Not assessed' },
  action: { fg: hex('#A8231C'), bg: hex('#FCE8E6'), short: 'Rule warning' },
}
type Tone = typeof TONES.normal
const NAMES: Record<string, string> = { heart_rate: 'Heart rate', respiratory_rate: 'Breathing rate', systolic_bp: 'Systolic BP', diastolic_bp: 'Diastolic BP', sleep_duration: 'Sleep duration', mood: 'Mood' }
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)
const two = (n: number) => String(n).padStart(2, '0')
const num = (s: string | null | undefined) => (s == null || s === '' ? null : Number(s))
/** Up to two decimals, a real minus sign, and "+" when asked. */
function fmt(n: number | null, signed = false, digits = 2) {
  if (n === null || !Number.isFinite(n)) return '—'
  const t = n.toLocaleString('en-US', { maximumFractionDigits: digits, useGrouping: false })
  return signed && Number(t) > 0 ? `+${t}` : t.replace('-', '−')
}
function utc(value: string | Date, time = true) {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  const date = `${two(d.getUTCDate())} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`
  return time ? `${date}, ${two(d.getUTCHours())}:${two(d.getUTCMinutes())} UTC` : date
}
/** One reference per check-in: profile code and check-in time, e.g. CHC-FE3-20300630-1200. */
function reference(result: MonitoringResult) {
  const d = new Date(result.timestamp)
  return `CHC-${profileCode(result.astronaut_id)}-${d.getUTCFullYear()}${two(d.getUTCMonth() + 1)}${two(d.getUTCDate())}-${two(d.getUTCHours())}${two(d.getUTCMinutes())}`
}
function wrap(s: string, font: PDFFont, size: number, width: number) {
  const lines: string[] = []
  let line = ''
  for (const word of s.split(/\s+/).filter(Boolean)) {
    const next = line ? `${line} ${word}` : word
    if (!line || font.widthOfTextAtSize(next, size) <= width) line = next
    else { lines.push(line); line = word }
  }
  return line ? [...lines, line] : lines
}
function fit(s: string, font: PDFFont, size: number, max: number) {
  if (font.widthOfTextAtSize(s, size) <= max) return s
  while (s.length > 1 && font.widthOfTextAtSize(`${s}…`, size) > max) s = s.slice(0, -1)
  return `${s.trimEnd()}…`
}
async function load(url: string) {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`A report asset could not be loaded (HTTP ${response.status}).`)
  return response.arrayBuffer()
}
async function fingerprint(result: MonitoringResult) {
  if (!globalThis.crypto?.subtle) return null // only available on localhost or HTTPS
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(result)))
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('')
}

export async function buildReport(input: ReportInput, now = new Date()): Promise<Uint8Array> {
  const { result, example, profile } = input
  const doc = await PDFDocument.create()
  doc.registerFontkit(fontkit)
  const [regular, medium, bold, logoBytes] = await Promise.all([interRegular, interMedium, interBold, logoUrl].map(load))
  // Whole fonts are embedded: fontkit's subsetting drops glyphs from Inter, which leaves gaps in the text.
  const F = { reg: await doc.embedFont(regular), med: await doc.embedFont(medium), bold: await doc.embedFont(bold), mono: await doc.embedFont(StandardFonts.Courier) }
  const logo = await doc.embedPng(logoBytes)
  const ref = reference(result), hash = await fingerprint(result)
  const pages: PDFPage[] = []
  let page!: PDFPage, y = 0 // y is the top of the next block, in points from the bottom of the page

  // ---- Drawing helpers ----
  type T = { font?: PDFFont; size?: number; color?: RGB; spacing?: number; align?: 'left' | 'right' | 'center' }
  const width = (s: string, o: T = {}) => (o.font ?? F.reg).widthOfTextAtSize(s, o.size ?? 8.5) + (o.spacing ?? 0) * s.length
  function text(s: string, x: number, baseline: number, o: T = {}) {
    const w = width(s, o), left = o.align === 'right' ? x - w : o.align === 'center' ? x - w / 2 : x
    if (o.spacing) page.pushOperators(setCharacterSpacing(o.spacing))
    page.drawText(s, { x: left, y: baseline, size: o.size ?? 8.5, font: o.font ?? F.reg, color: o.color ?? C.body })
    if (o.spacing) page.pushOperators(setCharacterSpacing(0))
  }
  /** A filled box whose upper edge is `top`; rounded corners are drawn as an SVG path (pdf-lib has no corner radius). */
  function box(x: number, top: number, w: number, h: number, color: RGB, r = 0, border?: RGB) {
    const k = Math.min(r, w / 2, h / 2), edge = border ? { borderColor: border, borderWidth: 0.6 } : {}
    if (k <= 0) { page.drawRectangle({ x, y: top - h, width: w, height: h, color, ...edge }); return }
    const path = `M${k},0 H${w - k} A${k},${k} 0 0 1 ${w},${k} V${h - k} A${k},${k} 0 0 1 ${w - k},${h} H${k} A${k},${k} 0 0 1 0,${h - k} V${k} A${k},${k} 0 0 1 ${k},0 Z`
    page.drawSvgPath(path, { x, y: top, color, ...edge })
  }
  const rule = (at: number, color = C.line, thickness = 0.6) => page.drawLine({ start: { x: M, y: at }, end: { x: W - M, y: at }, thickness, color })
  // The logo PNG has transparent margins: its visible part spans x 150–2025 and y 195–519 of 2172 × 724 pixels.
  function drawLogo(x: number, visibleTop: number, visibleHeight: number) {
    const s = visibleHeight / 324
    page.drawImage(logo, { x: x - 150 * s, y: visibleTop - visibleHeight - 205 * s, width: 2172 * s, height: 724 * s })
  }

  // ---- Pages: a full masthead on page 1, a slim one after ----
  function newPage() {
    page = doc.addPage([W, H]); pages.push(page)
    if (pages.length === 1) {
      box(0, H, W, 112, C.navy)
      page.drawRectangle({ x: 0, y: H - 114.5, width: W, height: 2.5, color: C.cyan })
      drawLogo(M, H - 38, 36)
      text('MISSION HEALTH MONITOR · MODE 1', W - M, H - 40, { font: F.bold, size: 6.8, color: C.cyan, spacing: 1.3, align: 'right' })
      text('Check-in assessment report', W - M, H - 62, { font: F.bold, size: 17, color: C.white, align: 'right' })
      text(`Ref. ${ref}   ·   Generated ${utc(now)}`, W - M, H - 80, { size: 7.5, color: C.mist, align: 'right' })
      y = H - 138
    } else {
      box(0, H, W, 34, C.navy)
      page.drawRectangle({ x: 0, y: H - 35.5, width: W, height: 1.5, color: C.cyan })
      drawLogo(M, H - 10, 14)
      text(`Check-in assessment report · Ref. ${ref} · continued`, W - M, H - 20, { size: 7, color: C.mist, align: 'right' })
      y = H - 62
    }
  }
  const room = (h: number) => { if (y - h < BOTTOM) newPage() }
  function section(n: string, title: string) {
    room(60); y -= 8
    text(n, M, y - 11, { font: F.bold, size: 7.5, color: C.teal, spacing: 1 })
    text(title, M + 20, y - 11, { font: F.bold, size: 11, color: C.ink })
    rule(y - 18, C.ink, 0.8); y -= 30
  }
  function para(s: string, o: T & { x?: number; w?: number; gap?: number } = {}) {
    const size = o.size ?? 8.5, lh = size * 1.45
    for (const line of wrap(s, o.font ?? F.reg, size, o.w ?? CW)) { room(lh); text(line, o.x ?? M, y - size, { ...o, size }); y -= lh }
    y -= o.gap ?? 4
  }
  function bullets(items: string[], color = C.teal) {
    for (const item of items) {
      wrap(item, F.reg, 8.5, CW - 14).forEach((line, i) => {
        room(12.3)
        if (!i) page.drawCircle({ x: M + 3, y: y - 5.6, size: 1.6, color })
        text(line, M + 12, y - 8.5); y -= 12.3
      })
      y -= 2
    }
  }
  type Col = { label: string; w: number; align?: 'left' | 'right' | 'center' }
  type Cell = string | ((x: number, mid: number, w: number) => void)
  const at = (c: Col, x: number) => (c.align === 'right' ? x + c.w - 6 : c.align === 'center' ? x + c.w / 2 : x + 6)
  function table(cols: Col[], rows: Cell[][], rowH = 24) {
    const head = () => {
      let x = M
      for (const c of cols) { text(c.label.toUpperCase(), at(c, x), y - 9, { font: F.bold, size: 6.2, color: C.muted, spacing: 0.6, align: c.align }); x += c.w }
      rule(y - 14, C.ink, 0.8); y -= 14
    }
    room(14 + rowH); head()
    rows.forEach((row, r) => {
      if (y - rowH < BOTTOM) { newPage(); head() }
      if (r % 2) page.drawRectangle({ x: M, y: y - rowH, width: CW, height: rowH, color: C.panel })
      let x = M
      row.forEach((cell, i) => {
        const c = cols[i], mid = y - rowH / 2
        if (typeof cell === 'function') cell(x, mid, c.w)
        else text(fit(cell, F.reg, 8.2, c.w - 12), at(c, x), mid - 2.9, { size: 8.2, align: c.align })
        x += c.w
      })
      y -= rowH
    })
    rule(y); y -= 10
  }
  const pill = (label: string, tone: Tone) => (x: number, mid: number, w: number) => {
    const pw = width(label, { font: F.med, size: 6.8 }) + 12
    box(x + (w - pw) / 2, mid + 6.5, pw, 13, tone.bg, 6.5)
    text(label, x + w / 2, mid - 2.4, { font: F.med, size: 6.8, color: tone.fg, align: 'center' })
  }
  /** Where the robust score sits on a −6 … +6 scale; the shaded band is −3.5 … +3.5. */
  const gauge = (z: number | null, tone: Tone) => (x: number, mid: number, w: number) => {
    if (z === null) { text('—', x + w / 2, mid - 2.9, { align: 'center', color: C.muted }); return }
    const L = x + 8, R = x + w - 8, pos = (v: number) => L + ((Math.max(-6, Math.min(6, v)) + 6) / 12) * (R - L)
    page.drawRectangle({ x: pos(-3.5), y: mid - 3, width: pos(3.5) - pos(-3.5), height: 6, color: C.band })
    page.drawLine({ start: { x: L, y: mid }, end: { x: R, y: mid }, thickness: 0.6, color: C.line })
    for (const t of [-3.5, 0, 3.5]) page.drawLine({ start: { x: pos(t), y: mid - (t ? 4 : 5) }, end: { x: pos(t), y: mid + (t ? 4 : 5) }, thickness: t ? 0.5 : 0.8, color: t ? C.mist : C.muted })
    page.drawCircle({ x: pos(z), y: mid, size: 3.3, color: tone.fg, borderColor: C.white, borderWidth: 1 })
    if (Math.abs(z) > 6) text(z > 0 ? '›' : '‹', z > 0 ? R + 2 : L - 6, mid - 3, { font: F.bold, size: 9, color: tone.fg })
  }
  const measurement = (e: Evidence) => (x: number, mid: number) => {
    text(NAMES[e.indicator] ?? cap(words(e.indicator)), x + 6, mid + 1.5, { font: F.med, size: 8.2, color: C.ink })
    text(e.value != null && e.unit ? e.unit : e.category != null ? 'self-reported' : '', x + 6, mid - 7.5, { size: 6.4, color: C.muted })
  }

  // ---- Page 1: header, notice, key facts and the overall result ----
  newPage()
  {
    const tag = 'SIMULATED DATA', tagW = width(tag, { font: F.bold, size: 6.5, spacing: 1 }) + 14
    const lines = wrap('Research prototype, not a diagnostic device. This report compares one check-in with the astronaut’s own synthetic history (fictional crew and readings). It is not medical advice.', F.reg, 7.6, CW - tagW - 34)
    const h = Math.max(30, lines.length * 11 + 14)
    box(M, y, CW, h, hex('#FFF8EC'), 6, hex('#F0D9AE'))
    box(M + 10, y - (h - 16) / 2, tagW, 16, C.navy, 8)
    text(tag, M + 17, y - (h - 16) / 2 - 10.6, { font: F.bold, size: 6.5, color: C.white, spacing: 1 })
    lines.forEach((line, i) => text(line, M + tagW + 22, y - (h - lines.length * 11) / 2 - 8.2 - i * 11, { size: 7.6 }))
    y -= h + 14
  }
  {
    const range = input.history?.astronauts.find(a => a.astronaut_id === result.astronaut_id)?.history.find(r => r.activity_context === result.activity_context)
    const facts: [string, string, string][] = [
      ['ASTRONAUT', profile.name, `Profile ID ${result.astronaut_id}`],
      ['CHECK-IN TIME', utc(result.timestamp), 'Mission calendar, UTC'],
      ['ACTIVITY CONTEXT', cap(words(result.activity_context)), 'Compared only within this context'],
      ['INPUT', example === null ? 'Saved check-in' : example ? 'Example values' : 'Entered by the user', example === null ? 'Example or manual: not recorded' : example ? 'Demo values filled by the app' : 'Manual entry'],
      ['PERSONAL HISTORY', range ? `Synthetic · ${range.observations} readings` : 'No history for this context', range ? `${utc(range.first, false)} – ${utc(range.last, false)}` : 'Nothing to compare with'],
      ['ASSESSED BY', 'Local backend', 'Personal statistics · nothing transmitted'],
    ]
    const gap = 8, cw = (CW - 2 * gap) / 3, ch = 46
    facts.forEach(([label, value, sub], i) => {
      const x = M + (i % 3) * (cw + gap), top = y - Math.floor(i / 3) * (ch + gap)
      box(x, top, cw, ch, C.panel, 6)
      text(label, x + 10, top - 13, { font: F.bold, size: 6.2, color: C.muted, spacing: 0.9 })
      text(fit(value, F.med, 9.5, cw - 20), x + 10, top - 27, { font: F.med, size: 9.5, color: C.ink })
      text(fit(sub, F.reg, 7, cw - 20), x + 10, top - 38.5, { size: 7, color: C.muted })
    })
    y -= 2 * (ch + gap) + 8
  }
  {
    const view = STATUS_VIEW[result.overall_status], tone = TONES[view.tone], leftW = CW - 170
    const lines = wrap(words(result.explanation), F.reg, 8.5, leftW - 36)
    const h = Math.max(86, 52 + lines.length * 12.3)
    box(M, y, CW, h, tone.bg, 8)
    box(M + 12, y - 14, 4, h - 28, tone.fg, 2)
    text('OVERALL RESULT', M + 28, y - 19, { font: F.bold, size: 6.5, color: tone.fg, spacing: 1.1 })
    text(view.label, M + 28, y - 38, { font: F.bold, size: 15, color: tone.fg })
    lines.forEach((line, i) => text(line, M + 28, y - 55 - i * 12.3))
    const rx = M + leftW
    page.drawLine({ start: { x: rx, y: y - 14 }, end: { x: rx, y: y - h + 14 }, thickness: 0.6, color: C.line })
    const pairs: [string, string, PDFFont][] = [['BODY SYSTEMS FLAGGED', result.affected_systems.map(s => cap(words(s))).join(', ') || 'None', F.med],
      ['BODY MARKER', result.body_marker ? cap(result.body_marker) : 'None', F.med], ['STATUS CODE', result.overall_status, F.mono]]
    pairs.forEach(([label, value, font], i) => {
      text(label, rx + 14, y - 19 - i * 22, { font: F.bold, size: 6.2, color: C.muted, spacing: 0.9 })
      text(fit(value, font, 8.6, 140), rx + 14, y - 30 - i * 22, { font, size: 8.6, color: C.ink })
    })
    y -= h + 10
  }

  // ---- 01: every measurement against the personal median ----
  section('01', 'Measurements compared with personal history')
  table([{ label: 'Measurement', w: 92 }, { label: 'Value', w: 48, align: 'right' }, { label: 'Median', w: 54, align: 'right' }, { label: 'Difference', w: 56, align: 'right' },
    { label: 'Score', w: 46, align: 'right' }, { label: 'Deviation', w: 92, align: 'center' }, { label: 'Readings', w: 42, align: 'right' }, { label: 'Status', w: CW - 430, align: 'center' }],
  result.evidence.map(e => {
    const s = e.statistics, value = num(e.value), base = num(e.baseline), z = num(s?.robust_z)
    const tone = s ? TONES[STATUS_VIEW[s.status].tone] : TONES.unavailable
    return [measurement(e), e.value ?? (e.category ? cap(e.category) : '—'), e.baseline ?? '—', value !== null && base !== null ? fmt(value - base, true) : '—',
      fmt(z, true), gauge(z, tone), s ? String(s.observation_count) : '—', pill(s ? tone.short : 'Not compared', tone)]
  }), 27)
  room(40)
  page.drawRectangle({ x: M, y: y - 8, width: 16, height: 6, color: C.band })
  text('Shaded band: robust score from −3.5 to +3.5. A score beyond it counts as unusual: an exploratory statistical cutoff, not a medical limit.', M + 22, y - 7.6, { size: 7, color: C.muted })
  y -= 14
  para('Score = 0.6745 × (value − personal median) ÷ MAD, where MAD is the median absolute deviation of the earlier readings. Readings = earlier readings compared: the latest 14 in the same activity context, at least 7 needed.', { size: 7, color: C.muted })

  // ---- 02: the statistics behind each comparison ----
  const compared = result.evidence.filter(e => e.statistics && (e.statistics.mad !== null || e.statistics.observation_count > 0)) // with earlier readings
  if (compared.length) {
    section('02', 'Statistical details')
    table([{ label: 'Measurement', w: 120 }, { label: 'MAD', w: 70, align: 'right' }, { label: 'Abs. deviation', w: 90, align: 'right' }, { label: 'History span', w: 80, align: 'right' },
      { label: 'Trend per day', w: 90, align: 'right' }, { label: 'Source', w: CW - 450, align: 'center' }],
    compared.map(e => {
      const s = e.statistics!
      return [measurement(e), fmt(num(s.mad)), fmt(num(s.absolute_deviation)), s.history_span_days ? `${fmt(num(s.history_span_days), false, 1)} days` : '—',
        s.trend_slope_per_day ? `${fmt(num(s.trend_slope_per_day), true)} ${e.unit}` : '—', s.history_origins.map(cap).join(', ') || '—']
    }), 27)
    para('The trend is the Theil–Sen median slope of the earlier readings. It describes the history only and never changes a status. A MAD of zero leaves the score unavailable.', { size: 7, color: C.muted })
  }

  // ---- 03 and 04: findings, gaps and the next step ----
  section('03', 'Findings')
  if (result.statistical_findings.length) bullets(result.statistical_findings.map(words))
  else para('No supported measurement went past the statistical cutoff.')
  if (result.insufficient_data.length) {
    room(30); y -= 2
    text('NOT ASSESSED', M, y - 7, { font: F.bold, size: 6.5, color: C.muted, spacing: 1 }); y -= 14
    bullets(result.insufficient_data.map(words), C.mist)
  }
  section('04', 'Next step')
  para(result.next_action_protocol_id
    ? `Approved action protocol: ${result.next_action_protocol_id}.`
    : 'No approved action protocol exists yet, so this report gives no treatment guidance. It is an exploratory monitoring result, not a diagnosis.')

  // ---- 05: this profile's recent saved check-ins ----
  if (input.recent?.length) {
    section('05', 'Recent check-ins for this profile')
    const short = { normal: 'No unusual pattern', unusual: 'Unusual', insufficient_data: 'Not assessed', rule_supported_warning: 'Rule warning' }
    table([{ label: 'Check-in time', w: 120 }, { label: 'Context', w: 92 }, { label: 'Heart rate', w: 62, align: 'right' }, { label: 'Blood pressure', w: 78, align: 'right' },
      { label: 'Breathing', w: 58, align: 'right' }, { label: 'Result', w: CW - 410, align: 'center' }],
    input.recent.slice(0, 5).map(c => {
      const i = c.check_in.indicators, status = c.assessment.overall_status
      return [utc(c.check_in.timestamp), cap(words(c.check_in.activity_context)), `${i.heart_rate.value} bpm`, `${i.systolic_bp.value}/${i.diastolic_bp.value} mmHg`,
        `${i.respiratory_rate.value} /min`, pill(short[status], TONES[STATUS_VIEW[status].tone])]
    }), 24)
  }

  // ---- 06: method, limits and a content fingerprint ----
  section(input.recent?.length ? '06' : '05', 'Method and limitations')
  ;[
    'Personal baseline: the median of the latest 14 earlier readings for the same astronaut, activity context, measurement protocol and unit. At least 7 are needed; otherwise the measurement is not assessed.',
    'The cutoff of 3.5 is an exploratory statistical value. It is not a medical threshold, and this report sets no health limits.',
    'Overall result: unusual when any compared measurement is unusual; no unusual pattern when at least one was compared and none is unusual; not assessed when none could be compared. Green does not establish healthy organ function.',
    'The history is synthetic: a fictional crew and readings. Real manual readings differ in protocol and cohort, which limits the comparison.',
    'Everything ran on this computer: the local backend assessed the check-in, and the browser made this PDF. Crew profiles are demo access control without passwords.',
  ].forEach((item, i) => {
    const lines = wrap(item, F.reg, 7.8, CW - 18)
    room(lines.length * 11.2 + 3)
    text(`${i + 1}`, M, y - 7.8, { font: F.bold, size: 7.8, color: C.teal })
    lines.forEach((line, j) => text(line, M + 14, y - 7.8 - j * 11.2, { size: 7.8 }))
    y -= lines.length * 11.2 + 4
  })
  if (hash) {
    room(58); y -= 6
    box(M, y, CW, 50, C.panel, 6)
    text('CONTENT FINGERPRINT · SHA-256', M + 12, y - 14, { font: F.bold, size: 6.2, color: C.muted, spacing: 0.9 })
    text(hash, M + 12, y - 27, { font: F.mono, size: 7.6, color: C.ink })
    text('Computed over the assessment data in this report, as received from the local backend. It identifies this exact content; it is not a signature.', M + 12, y - 40, { size: 6.6, color: C.muted })
    y -= 56
  }

  // ---- Footer on every page, now that the page count is known ----
  pages.forEach((p, i) => {
    page = p
    rule(46)
    text('CREW HEALTH COMPASS · MISSION HEALTH MONITOR · SIMULATED DATA', M, 34, { font: F.bold, size: 6, color: C.muted, spacing: 0.8 })
    text(`Ref. ${ref}   ·   Page ${i + 1} of ${pages.length}`, W - M, 34, { size: 6.8, color: C.muted, align: 'right' })
    text('Research prototype, not a diagnostic device. Made on this computer; no data was transmitted.', M, 23, { size: 6.5, color: C.muted })
  })
  doc.setTitle(`Check-in assessment report · ${profile.name} · ${utc(result.timestamp)}`)
  doc.setAuthor('Crew Health Compass (local research prototype)')
  doc.setSubject('Mode 1 check-in compared with the astronaut’s own synthetic history. Not a diagnostic document.')
  doc.setKeywords(['Crew Health Compass', 'Mode 1', 'simulated data', ref])
  doc.setCreator('Crew Health Compass'); doc.setProducer('pdf-lib')
  doc.setLanguage('en'); doc.setCreationDate(now); doc.setModificationDate(now)
  return doc.save()
}

export const reportFileName = (result: MonitoringResult) => `Crew-Health-Report-${reference(result)}.pdf`
