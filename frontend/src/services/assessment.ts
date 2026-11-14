import type { Assessment, MockData } from '../types/assessment'

export async function loadMockData(signal: AbortSignal): Promise<MockData> {
  const response = await fetch(`${import.meta.env.BASE_URL}mock/assessment.json`, { signal })
  if (!response.ok) throw new Error(`Unable to load the prototype data (${response.status}).`)
  return response.json()
}

// This adapter selects response fixtures; it does not classify measurements.
export function selectAssessment(data: MockData, crew: string, visit: string, simulated: boolean): Assessment {
  const assessment = structuredClone(data.snapshots[crew][visit])
  if (simulated) {
    for (const system of assessment.systems) {
      const fixture = data.dailyDemo.snapshots[visit][system.id]
      if (!fixture) continue
      const { marker, ...status } = structuredClone(fixture)
      Object.assign(system, status)
      system.markers.unshift(marker)
      system.defaultMarker = marker.id
    }
  }
  return assessment
}
