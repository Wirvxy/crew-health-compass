// Prototype-only view models. Replace the adapter when A publishes shared contracts.
export type Status = 'normal' | 'watch' | 'action' | 'unavailable'
export type SystemId = 'cardio' | 'immune' | 'metabolic' | 'sleep'
export type Provenance = 'user' | 'simulated' | 'dataset:OSD-575'
export interface Marker {
  id: string; name: string; panel: string; unit: string; value: number | null
  baseline: number | null; baselineCount: number
  reference: { low: number | null; high: number | null }
  trend: { time: string; value: number | null }[]
  provenance: Provenance; source: { title: string; url: string; column: string }
}
export interface SystemAssessment {
  id: SystemId; name: string; status: Status; statusProvenance: string
  reason: string; action: string; summary: string
  source: { title: string; url: string }; drift: { visible: boolean; text?: string }
  defaultMarker: string | null; markers: Marker[]
}
export interface Assessment {
  astronautId: string; timepoint: string; context: string
  systems: SystemAssessment[]
}
export type DailyField = 'context' | 'timestamp' | 'heart' | 'respiratory' | 'systolic' | 'diastolic' | 'sleep' | 'mood'
export type DailyDraft = Record<DailyField, string>
export interface CheckIn {
  astronautId: string; values: DailyDraft; provenance: 'user' | 'simulated'; timestamp: string
}
export interface CrewDraft { values: DailyDraft; simulated: boolean }
export interface MockData {
  crew: string[]; timepoints: string[]; baselineMethod: string
  snapshots: Record<string, Record<string, Assessment>>
  dailyDemo: {
    values: Record<DailyField, string | number>
    snapshots: Record<string, Partial<Record<SystemId, Omit<SystemAssessment, 'id' | 'name' | 'markers' | 'defaultMarker' | 'drift'> & { marker: Marker }>>>
  }
}
