// Export the PDF report: a Web Worker builds it (services/report.ts), then the browser saves it. Nothing leaves this computer.
import type { ReportInput } from './report'
import type { ReportReply } from './reportWorker'

export function exportReport(input: ReportInput): Promise<void> {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL('./reportWorker.ts', import.meta.url), { type: 'module' })
    worker.onmessage = (event: MessageEvent<ReportReply>) => {
      worker.terminate()
      if ('error' in event.data) { reject(new Error(event.data.error)); return }
      const url = URL.createObjectURL(new Blob([new Uint8Array(event.data.pdf)], { type: 'application/pdf' })), a = document.createElement('a')
      a.href = url; a.download = event.data.filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
      resolve()
    }
    worker.onerror = event => { worker.terminate(); reject(new Error(event.message || 'The report worker failed.')) }
    worker.postMessage(input)
  })
}
