import type { Status } from '../types/assessment'
export const statuses = {
  normal: { icon: '✓', label: 'Normal' }, watch: { icon: '▲', label: 'Watch' },
  action: { icon: '●', label: 'Action needed' }, unavailable: { icon: '○', label: 'Not assessed' },
}
export default function StatusLabel({ status, label }: { status: Status; label?: string }) {
  return <span className={`status ${status}`}><span className="status-icon" aria-hidden="true">{statuses[status].icon}</span>{label ?? statuses[status].label}</span>
}
