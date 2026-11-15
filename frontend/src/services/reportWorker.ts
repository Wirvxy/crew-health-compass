// Background thread (Web Worker) that builds the PDF report, so the page stays responsive meanwhile.
import { buildReport, reportFileName } from './report'
import type { ReportInput } from './report'

export type ReportReply = { pdf: Uint8Array; filename: string } | { error: string }

self.onmessage = async (event: MessageEvent<ReportInput>) => {
  let reply: ReportReply
  try { reply = { pdf: await buildReport(event.data), filename: reportFileName(event.data.result) } }
  catch (error) { reply = { error: error instanceof Error ? error.message : String(error) } }
  self.postMessage(reply)
}
