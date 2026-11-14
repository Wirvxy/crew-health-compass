// Validate consumed fields at the boundary; preserve the complete original response unchanged.
import type { CrewList, PanelList, History, Postflight, TrajectoryResponse, Comparison } from '../types/dataset'
type Rule = (value: unknown) => boolean
const text: Rule = v => typeof v === 'string'
const number: Rule = v => typeof v === 'number' && Number.isFinite(v)
const decimal: Rule = v => v === null || (typeof v === 'string' && /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(v) && Number.isFinite(Number(v)))
const nullable = (rule: Rule): Rule => v => v === null || rule(v)
const list = (rule: Rule): Rule => v => Array.isArray(v) && v.every(rule)
const shape = (fields: Record<string, Rule>): Rule => v => v !== null && typeof v === 'object' && Object.entries(fields).every(([key,rule]) => rule((v as Record<string,unknown>)[key]))
const oneOf = (...values: string[]): Rule => v => typeof v === 'string' && values.includes(v)
const source = shape({file:text,row:number,value_column:text})
const identity = {crew_id:text,panel:text,biomarker:text}
const baseline = {baseline_value:decimal,baseline_status:oneOf('complete','insufficient_baseline','incompatible_units'),baseline_sample_count:number}
const lab = oneOf('within','below','above','unavailable')
const valueStatus = oneOf('valid','missing','invalid')
const envelope = {study_id:oneOf('OSD-575'),provenance:oneOf('dataset:OSD-575'),note:text}
const visit = shape({visit:text,phase_day:number,value:decimal,value_status:valueStatus,change_from_baseline:decimal,distance_from_baseline:decimal,distance_movement:nullable(oneOf('closer','farther','unchanged')),lab_comparison:lab,source})
const trajectory = shape({...identity,...baseline,unit:text,trajectory_classification:oneOf('consistently_closer','consistently_farther','mixed','unchanged_distance','insufficient_data'),visits:list(visit),finding:text,evidence_limitations:list(text),provenance:envelope.provenance})
const schemas = {
  astronauts: shape({...envelope,astronauts:list(shape({crew_id:text,visits:list(text)}))}),
  panels: shape({...envelope,panels:list(shape({panel:oneOf('cmp','eve_cardiovascular','eve_immune','alamar_immune'),group:text,biomarkers:list(shape({biomarker:text,unit:text}))}))}),
  measurements: shape({...envelope,measurements:list(shape({...identity,visit:text,value:decimal,value_status:valueStatus,unit:text,lab_ref_min:decimal,lab_ref_max:decimal,source,provenance:envelope.provenance}))}),
  postflight: shape({...envelope,results:list(shape({...identity,...baseline,visit:text,current_value:decimal,current_value_status:valueStatus,unit:text,absolute_change:decimal,percentage_change:decimal,change_direction:oneOf('increase','decrease','unchanged','unavailable'),lab_comparison:lab,lab_ref_min:decimal,lab_ref_max:decimal,source,provenance:envelope.provenance,analysis_notes:list(text)}))}),
  trajectory: shape({...envelope,classification_note:text,trajectory}),
  comparison: shape({...envelope,classification_note:text,trajectories:list(trajectory)}),
}
interface Results { astronauts:CrewList; panels:PanelList; measurements:History; postflight:Postflight; trajectory:TrajectoryResponse; comparison:Comparison }
export function decodeDataset<K extends keyof Results>(kind: K, value: unknown): Results[K] {
  if (!schemas[kind](value)) throw new Error(`Unexpected ${kind} response. The dataset API contract may have changed.`)
  return value as Results[K]
}
